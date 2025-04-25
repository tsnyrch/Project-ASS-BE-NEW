import bcrypt from "bcryptjs";
import { Request, Response } from "express";
import jwt from "jsonwebtoken";
import {
  authEnv,
  generateAccessToken,
  generateRefreshToken,
} from "../middleware/auth";
import User from "../model/User";
import UserRepository from "../repositories/UserRepository";
import ResponseError from "../utils/ResponseError";

interface LoginRequest {
  userName: string;
  password: string;
}

interface RefreshTokenRequest {
  userName: string;
  refreshToken: string;
}

export default class UserController {
  private repository: UserRepository;

  constructor() {
    this.repository = new UserRepository();
  }

  getUsers = async (req: Request, res: Response): Promise<Response> => {
    try {
      const users: User[] = await this.repository.getAllUsers();
      return res.json(users);
    } catch (error) {
      throw new ResponseError(
        `Failed to get users: ${(error as Error).message}`,
        500,
      );
    }
  };

  createUser = async (req: Request, res: Response): Promise<Response> => {
    try {
      // This should be removed in production
      await User.truncate(); // will delete all users TODO delete later on

      if (!req.body || !req.body.userName || !req.body.password) {
        throw new ResponseError("Missing required user fields", 400);
      }

      const user: User = req.body;
      const createdUser: User = await User.create({ ...user });
      return res.json(createdUser);
    } catch (error) {
      throw new ResponseError(
        `Failed to create user: ${(error as Error).message}`,
        500,
      );
    }
  };

  private sendLoginResponse = (
    user: User,
    userId: number,
    res: Response,
  ): Response => {
    try {
      const accessToken = generateAccessToken(user);
      const refreshToken = generateRefreshToken(userId);
      this.repository.updateUserRefreshToken(userId, refreshToken);
      return res.json({
        id: userId,
        userName: user.userName,
        firstName: user.firstName,
        lastName: user.lastName,
        isAdmin: user.isAdmin,
        accessToken: accessToken,
        refreshToken: refreshToken,
      });
    } catch (error) {
      throw new ResponseError(
        `Failed to generate tokens: ${(error as Error).message}`,
        500,
      );
    }
  };

  getUserById = async (req: Request, res: Response): Promise<Response> => {
    try {
      const id = parseInt(req.params.id);

      if (isNaN(id)) {
        throw new ResponseError("Invalid user ID", 400);
      }

      const user: User | null = await this.repository.getUserById(id);

      if (!user) {
        throw new ResponseError("User not found", 404);
      }

      return res.json(user);
    } catch (error) {
      const err = error as ResponseError;
      throw new ResponseError(
        `Failed to get user: ${err.message}`,
        err.statusCode || 500,
      );
    }
  };

  register = async (req: Request, res: Response): Promise<Response> => {
    // Currently just returns an empty response
    return res.send();
    // Commented implementation that might be used in the future
    /*
    const user = req.body;
    await this.repository.createUser(user);
    return await this.login(req, res);
    */
  };

  login = async (req: Request, res: Response): Promise<Response> => {
    try {
      const { userName, password } = req.body as LoginRequest;

      if (!userName || !password) {
        throw new ResponseError("Username and password are required", 400);
      }

      const foundUser = await this.repository.getUserByUserName(userName);

      if (!foundUser) {
        throw new ResponseError("Incorrect credentials", 401);
      }

      const isMatch = await bcrypt.compare(password, foundUser.password);

      if (isMatch) {
        return this.sendLoginResponse(foundUser, foundUser.id, res);
      } else {
        throw new ResponseError("Incorrect credentials", 401);
      }
    } catch (error) {
      const err = error as ResponseError;
      throw new ResponseError(
        `Login failed: ${err.message}`,
        err.statusCode || 500,
      );
    }
  };

  refreshToken = async (req: Request, res: Response): Promise<Response> => {
    try {
      const { userName, refreshToken } = req.body as RefreshTokenRequest;

      if (!refreshToken || !userName) {
        throw new ResponseError(
          "Both username and refresh token are required",
          400,
        );
      }

      const foundUser = await this.repository.getUserByUserName(userName);

      if (!foundUser) {
        throw new ResponseError("User does not exist", 404);
      }

      try {
        jwt.verify(refreshToken, authEnv.REFRESH_TOKEN_SECRET);
      } catch (tokenError) {
        await this.repository.deleteUserRefreshToken(foundUser.id);
        throw new ResponseError("Cannot verify refresh token", 401);
      }

      if (foundUser.refreshToken !== refreshToken) {
        await this.repository.deleteUserRefreshToken(foundUser.id);
        throw new ResponseError("Invalid refresh token", 401);
      }

      const accessToken = generateAccessToken(foundUser);
      const newRefreshToken = generateRefreshToken(foundUser.id);
      await this.repository.updateUserRefreshToken(
        foundUser.id,
        newRefreshToken,
      );

      return res.json({
        accessToken: accessToken,
        refreshToken: newRefreshToken,
      });
    } catch (error) {
      const err = error as ResponseError;
      throw new ResponseError(
        `Token refresh failed: ${err.message}`,
        err.statusCode || 500,
      );
    }
  };
}

import { Request, Response } from "express";
import fs from "fs";
import MeasurementConfig from "../model/MeasurementConfig";
import SettingsRepository from "../repositories/SettingsRepository";
import CronScheduler from "../services/CronScheduler";
import ResponseError from "../utils/ResponseError";

export class SettingsController {
  private repository: SettingsRepository;

  constructor() {
    this.repository = new SettingsRepository();
  }

  getMeasurementConfig = async (
    req: Request,
    res: Response,
  ): Promise<Response> => {
    try {
      const actualConfig = await this.repository.getMeasurementConfig();
      return res.json(actualConfig);
    } catch (error) {
      throw new ResponseError(
        `Failed to get measurement config: ${(error as Error).message}`,
        500,
      );
    }
  };

  updateMeasurementConfig = async (
    req: Request,
    res: Response,
  ): Promise<Response> => {
    try {
      if (!req.body) {
        throw new ResponseError("Missing request body", 400);
      }

      const newConfig: MeasurementConfig = req.body;

      // Validate required fields
      if (
        !newConfig.firstMeasurement ||
        newConfig.measurementFrequency === undefined ||
        newConfig.lengthOfAE === undefined
      ) {
        throw new ResponseError("Missing required configuration fields", 400);
      }

      // Ensure measurementFrequency is a number
      newConfig.measurementFrequency = parseInt(
        newConfig.measurementFrequency.toString(),
      );

      if (isNaN(newConfig.measurementFrequency)) {
        throw new ResponseError(
          "Measurement frequency must be a valid number",
          400,
        );
      }

      const oldConfig = await this.repository.getMeasurementConfig();

      // Validate date format
      const firstMeasurementDate = new Date(newConfig.firstMeasurement);
      if (isNaN(firstMeasurementDate.getTime())) {
        throw new ResponseError(
          "Invalid date format for firstMeasurement",
          400,
        );
      }

      // Validate measurement frequency
      if (newConfig.measurementFrequency <= newConfig.lengthOfAE) {
        throw new ResponseError(
          "Measurement frequency must be greater than length of AE",
          400,
        );
      }

      // Update scheduler if frequency changed
      if (newConfig.measurementFrequency !== oldConfig.measurementFrequency) {
        CronScheduler.getInstance().setNewSchedule(
          newConfig.measurementFrequency,
          new Date(newConfig.firstMeasurement),
        );
      }

      // TODO - change this after multispectral is functional
      newConfig.multispectralCamera = false;

      return new Promise((resolve, reject) => {
        fs.writeFile(
          this.repository.measurementConfigPath,
          JSON.stringify(newConfig, null, 2),
          (err) => {
            if (err) {
              console.error("Error writing config file:", err);
              reject(
                new ResponseError(
                  `Failed to update configuration: ${err.message}`,
                  500,
                ),
              );
            } else {
              resolve(res.json(newConfig));
            }
          },
        );
      });
    } catch (error) {
      const err = error as ResponseError;
      throw new ResponseError(
        `Failed to update measurement config: ${err.message}`,
        err.statusCode || 500,
      );
    }
  };
}

import { Request, Response } from "express";
import fs from "fs";
import MeasurementInfo from "../model/MeasurementInfo";
import { MeasurementRepository } from "../repositories/MeasurementRepository";
import SettingsRepository from "../repositories/SettingsRepository";
import CronScheduler from "../services/CronScheduler";
import { MeasurementService } from "../services/MeasurementService";
import ResponseError from "../utils/ResponseError";
// @ts-ignore
import archiver from "archiver";

export class MeasurementController {
  private service: MeasurementService;
  private repository: MeasurementRepository;
  private settingsRepository: SettingsRepository;

  constructor() {
    this.service = new MeasurementService();
    this.repository = new MeasurementRepository();
    this.settingsRepository = new SettingsRepository();
  }

  getLatestMeasurement = async (
    req: Request,
    res: Response,
  ): Promise<Response> => {
    try {
      const latestMeasurementsInfo =
        await this.repository.getLatestMeasurementInfo();
      const plannedMeasurement: Date | null =
        CronScheduler.getInstance().nextScheduledDate;

      return res.json({
        lastBackup: new Date("2024-04-22T23:00:00"),
        lastMeasurement:
          latestMeasurementsInfo.length > 0
            ? latestMeasurementsInfo[0].date_time
            : null,
        plannedMeasurement: plannedMeasurement,
        latestMeasurement: latestMeasurementsInfo,
      });
    } catch (error) {
      throw new ResponseError(
        `Failed to get latest measurement: ${(error as Error).message}`,
      );
    }
  };

  getMeasurementHistory = async (
    req: Request,
    res: Response,
  ): Promise<Response> => {
    if (!req.query.startDate || !req.query.endDate) {
      throw new ResponseError(
        "Missing required parameters: startDate and endDate",
        400,
      );
    }

    const startDate = new Date(req.query.startDate as string);
    const endDate = new Date(req.query.endDate as string);

    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      throw new ResponseError("Invalid date format", 400);
    }

    try {
      const measurementsHistory = await this.repository.getMeasurementHistory(
        startDate,
        endDate,
      );
      return res.json(measurementsHistory);
    } catch (error) {
      throw new ResponseError(
        `Failed to get measurement history: ${(error as Error).message}`,
      );
    }
  };

  getMeasurementById = async (req: Request, res: Response): Promise<any> => {
    const id = parseInt(req.params.id);

    if (isNaN(id)) {
      throw new ResponseError("Invalid ID format", 400);
    }

    try {
      const measurement = await this.repository.getMeasurementById(id);

      if (!measurement) {
        return res.status(404).send("Measurement not found");
      }

      // TODO: - Use real data
      const dir: string = "./mock";
      const files = fs
        .readdirSync(dir)
        .filter(
          (file) =>
            file.endsWith(".png") &&
            file.startsWith(
              `${id}_${measurement.date_time
                .toISOString()
                .split(":")
                .join("-")}`,
            ),
        );

      if (files.length === 0) {
        return res.status(404).send("No files found for this measurement");
      }

      const fileName = `measurement_${id}.zip`;
      const output = fs.createWriteStream(`${dir}/${fileName}`);
      const archive = archiver("zip", {
        zlib: { level: 9 },
      });

      output.on("close", () => {
        res.download(
          `${dir}/${fileName}`,
          fileName,
          (err: NodeJS.ErrnoException | null) => {
            if (err) {
              console.error("Error sending file:", err);
            }
            // Cleanup: delete the ZIP file after sending the response
            try {
              fs.unlinkSync(`${dir}/${fileName}`);
            } catch (unlinkErr) {
              console.error("Error deleting zip file:", unlinkErr);
            }
          },
        );
      });

      archive.on("error", (err) => {
        throw new ResponseError(`Archive error: ${err.message}`, 500);
      });

      archive.pipe(output);

      files.forEach((file) => {
        archive.append(fs.createReadStream(`${dir}/${file}`), { name: file });
      });

      archive.finalize();
      return archive;
    } catch (error) {
      throw new ResponseError(
        `Failed to get measurement: ${(error as Error).message}`,
      );
    }
  };

  startMeasurement = async (req: Request, res: Response): Promise<Response> => {
    try {
      const measurementRes = await this.startMeasurementLogic();
      return res.json(measurementRes);
    } catch (error) {
      throw new ResponseError(
        `Failed to start measurement: ${(error as Error).message}`,
      );
    }
  };

  startMeasurementLogic = async (
    scheduled = false,
  ): Promise<MeasurementInfo> => {
    console.log("Starting measurement with config:");
    console.log("Scheduled:", scheduled);

    try {
      const config = await this.settingsRepository.getMeasurementConfig();
      console.log("Config:", config);

      const newMeasurement = await MeasurementInfo.create({
        date_time: new Date(),
        rgbCamera: config.rgbCamera,
        multispectralCamera: config.multispectralCamera,
        numberOfSensors: config.numberOfSensors,
        lengthOfAE: config.lengthOfAE,
        scheduled: scheduled,
      });

      console.log("Created measurement with ID:", newMeasurement.id);

      // Commented out for now as these are placeholders
      /*
      if (config.rgbCamera) {
        const serviceRgbResponse = await this.service.startRgbMeasurement(
          newMeasurement.id, newMeasurement.dateTime, 1
        );
        if (serviceRgbResponse.status === ResponseStatus.ERROR) {
          await this.repository.deleteNewMeasurement(newMeasurement);
          throw new ResponseError(serviceRgbResponse.error, 500);
        }
      }
      */

      return await this.repository.saveNewMeasurement(newMeasurement);
    } catch (error) {
      throw new ResponseError(
        `Error in measurement logic: ${(error as Error).message}`,
        500,
      );
    }
  };
}
import { NextFunction, Request, Response } from "express";
import jwt, { JwtPayload } from "jsonwebtoken";

import { load } from "ts-dotenv";
import User from "../model/User";
import ResponseError from "../utils/ResponseError";

export const authEnv = load({
  ACCESS_TOKEN_SECRET: String,
  REFRESH_TOKEN_SECRET: String,
});

export interface TokenPayload extends JwtPayload {
  id: number;
  userName: string;
  firstName?: string;
  lastName?: string;
}

export interface AuthenticatedRequest extends Request {
  token: TokenPayload;
  user?: User;
}

/**
 * Authentication middleware that verifies the JWT token from the request headers
 * and attaches the decoded token payload to the request object
 */
export const auth = async (
  req: Request,
  res: Response,
  next: NextFunction,
): Promise<void> => {
  try {
    const authHeader = req.header("Authorization");

    if (!authHeader) {
      throw new ResponseError("No authorization header provided", 401);
    }

    const token = authHeader.replace("Bearer ", "");

    if (!token) {
      throw new ResponseError("No token provided", 401);
    }

    try {
      const decoded = jwt.verify(
        token,
        authEnv.ACCESS_TOKEN_SECRET,
      ) as TokenPayload;
      (req as AuthenticatedRequest).token = decoded;
      next();
    } catch (jwtError) {
      throw new ResponseError("Invalid or expired token", 401);
    }
  } catch (err) {
    const error = err as ResponseError;
    res.status(error.statusCode || 401).json({
      error: error.message || "Please authenticate",
      code: error.statusCode || 401,
    });
  }
};

/**
 * Generates a short-lived access token for the authenticated user
 */
export function generateAccessToken(user: User): string {
  if (!user || !user.id) {
    throw new Error("Invalid user data for token generation");
  }

  return jwt.sign(
    {
      id: user.id,
      userName: user.userName,
      firstName: user.firstName,
      lastName: user.lastName,
    },
    authEnv.ACCESS_TOKEN_SECRET,
    {
      expiresIn: "5m",
    },
  );
}

/**
 * Generates a long-lived refresh token for token renewal
 */
export function generateRefreshToken(userId: number): string {
  if (!userId) {
    throw new Error("Invalid user ID for refresh token generation");
  }

  return jwt.sign(
    {
      id: userId,
    },
    authEnv.REFRESH_TOKEN_SECRET,
    {
      expiresIn: "90d",
    },
  );
}
import bcrypt from "bcryptjs";
import { DataTypes, Model } from "sequelize";
import { sequelize } from "../config/db.config";

/**
 * User model representing application users
 */
export default class User extends Model {
  declare id: number;
  declare firstName: string;
  declare lastName: string;
  declare userName: string;
  declare password: string;
  declare isAdmin: boolean;
  declare refreshToken: string | null;

  /**
   * Validates a password against the user's stored hash
   * @param password The password to validate
   * @returns True if password matches, false otherwise
   */
  async validatePassword(password: string): Promise<boolean> {
    return await bcrypt.compare(password, this.password);
  }
}

User.init(
  {
    id: {
      type: DataTypes.INTEGER,
      autoIncrement: true,
      primaryKey: true,
    },
    firstName: {
      type: DataTypes.STRING,
      allowNull: true,
    },
    lastName: {
      type: DataTypes.STRING,
      allowNull: true,
    },
    userName: {
      type: DataTypes.STRING,
      allowNull: false,
      unique: true,
      validate: {
        len: [3, 50],
        notEmpty: true,
      },
    },
    password: {
      type: DataTypes.STRING,
      allowNull: false,
      validate: {
        notEmpty: true,
      },
    },
    isAdmin: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
    },
    refreshToken: {
      type: DataTypes.STRING,
      allowNull: true,
    },
  },
  {
    sequelize,
    tableName: "users",
    timestamps: true, // Add createdAt and updatedAt timestamps
  },
);

/**
 * Hash password before saving a new user or updating an existing user's password
 */
User.addHook("beforeSave", async (user: User) => {
  // Only hash the password if it was changed (or is new)
  if (!user.changed("password")) {
    return;
  }

  try {
    // Use a stronger salt round (12) for better security
    const salt = await bcrypt.genSalt(12);
    user.password = await bcrypt.hash(user.password, salt);
  } catch (error) {
    console.error("Error hashing password:", error);
    throw new Error("Failed to hash password");
  }
});
import { sequelize } from "../config/db.config";
import MeasurementInfo from "./MeasurementInfo";
import User from "./User";

/**
 * Initialize all model associations and complete setup
 * This should be called after database connection is established
 * but before any model is used
 */
export const initializeModels = async (): Promise<void> => {
  // Define model associations here if needed
  // Example: User.hasMany(MeasurementInfo);

  // Sync models with database
  // In production, you might want to use { alter: true } or no sync at all
  // depending on your migration strategy
  try {
    await sequelize.sync();
    console.log("Models synchronized with database");
  } catch (error) {
    console.error("Failed to synchronize models with database:", error);
    throw error;
  }
};

// Export all models for convenience
export { MeasurementInfo, User };
import { DataTypes, Model } from "sequelize";
import { sequelize } from "../config/db.config";

/**
 * Model representing measurement information and configuration
 */
export default class MeasurementInfo extends Model {
  declare id: number;
  declare date_time: Date;
  declare rgbCamera: boolean;
  declare multispectralCamera: boolean;
  declare numberOfSensors: number;
  declare lengthOfAE: number;
  declare scheduled: boolean;

  // Virtuals and additional properties from Sequelize
  declare readonly createdAt: Date;
  declare readonly updatedAt: Date;
}

MeasurementInfo.init(
  {
    id: {
      type: DataTypes.INTEGER,
      autoIncrement: true,
      primaryKey: true,
    },
    date_time: {
      type: DataTypes.DATE,
      allowNull: false,
      validate: {
        isDate: true,
      },
    },
    rgbCamera: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      defaultValue: false,
    },
    multispectralCamera: {
      type: DataTypes.BOOLEAN,
      allowNull: false,
      defaultValue: false,
    },
    numberOfSensors: {
      type: DataTypes.INTEGER,
      allowNull: false,
      validate: {
        min: 0,
        max: 100, // Assuming a reasonable maximum
      },
    },
    lengthOfAE: {
      type: DataTypes.FLOAT,
      allowNull: false,
      validate: {
        min: 0,
      },
    },
    scheduled: {
      type: DataTypes.BOOLEAN,
      defaultValue: false,
    },
  },
  {
    sequelize,
    tableName: "measurement_info",
    timestamps: true, // Add createdAt and updatedAt timestamps
    indexes: [
      {
        name: "idx_datetime",
        fields: ["date_time"], // Index for faster date-based queries
      },
      {
        name: "idx_scheduled",
        fields: ["scheduled"], // Index for faster scheduled queries
      },
    ],
  },
);
/**
 * Configuration interface for measurement parameters
 */
export default interface MeasurementConfig {
  /**
   * Frequency of measurements in minutes
   * Must be greater than lengthOfAE
   */
  measurementFrequency: number;

  /**
   * Date and time of the first scheduled measurement
   */
  firstMeasurement: Date;

  /**
   * Flag indicating whether RGB camera should be used during measurement
   */
  rgbCamera: boolean;

  /**
   * Flag indicating whether multispectral camera should be used during measurement
   * Currently not functional (see SettingsController)
   */
  multispectralCamera: boolean;

  /**
   * Number of sensors to use for the measurement
   */
  numberOfSensors: number;

  /**
   * Length of acoustic emission measurement in minutes
   * Must be less than measurementFrequency
   */
  lengthOfAE: number;
}
import { Router } from "express";
import UserController from "../controllers/UserController";
import { catchAsync } from "../utils/catchAsync";
import { auth } from "../middleware/auth";

/**
 * Router for user-related endpoints
 */
const router: Router = Router();
const controller: UserController = new UserController();

/**
 * GET /users - Get all users (admin)
 * POST /users - Create a new user (admin)
 * Both routes are protected by authentication
 */
router
  .route("/")
  .get(auth, catchAsync(controller.getUsers))
  .post(auth, catchAsync(controller.createUser));

/**
 * POST /users/login - Authenticate a user
 * Public route, no authentication required
 */
router.route("/login").post(catchAsync(controller.login));

/**
 * POST /users/register - Register a new user
 * Public route, no authentication required
 */
router.route("/register").post(catchAsync(controller.register));

/**
 * POST /users/refreshToken - Refresh an access token using a refresh token
 * Public route, token validation handled in controller
 */
router.route("/refreshToken").post(catchAsync(controller.refreshToken));

/**
 * GET /users/:id - Get a user by ID
 * Protected by authentication
 */
router.route("/:id").get(auth, catchAsync(controller.getUserById));

export default router;
import { Router } from "express";
import { catchAsync } from "../utils/catchAsync";
import { SettingsController } from "../controllers/SettingsController";
import { auth } from "../middleware/auth";

/**
 * Router for application settings endpoints
 */
const router = Router();
const controller = new SettingsController();

/**
 * GET /settings/measurementConfig - Get the current measurement configuration
 * PUT /settings/measurementConfig - Update the measurement configuration
 * Both routes are protected by authentication
 */
router
  .route("/measurementConfig")
  .get(auth, catchAsync(controller.getMeasurementConfig))
  .put(auth, catchAsync(controller.updateMeasurementConfig));

export default router;
import { Router } from "express";
import { catchAsync } from "../utils/catchAsync";
import { MeasurementController } from "../controllers/MeasurementController";
import MeasurementInfo from "../model/MeasurementInfo";
import { auth } from "../middleware/auth";

/**
 * Router for measurement-related endpoints
 */
const router = Router();
const controller = new MeasurementController();

/**
 * GET /measurements/start - Start a new measurement
 * Protected by authentication
 */
router.route("/start").get(auth, catchAsync(controller.startMeasurement));

/**
 * GET /measurements/latest - Get the latest measurement data
 * Protected by authentication
 */
router.route("/latest").get(auth, catchAsync(controller.getLatestMeasurement));

/**
 * GET /measurements/history - Get measurement history within a date range
 * Protected by authentication
 * Query parameters:
 * - startDate: ISO date string for the start of the range
 * - endDate: ISO date string for the end of the range
 */
router
  .route("/history")
  .get(auth, catchAsync(controller.getMeasurementHistory));

/**
 * GET /measurements/all - Get all measurements (mainly for debugging)
 * Protected by authentication
 */
router.route("/all").get(
  auth,
  catchAsync(async (req, res) => {
    const data = await MeasurementInfo.findAll({
      order: [["dateTime", "DESC"]],
    });
    res.json(data);
  }),
);

/**
 * GET /measurements/:id - Get a specific measurement by ID
 * Protected by authentication
 */
router.route("/:id").get(auth, catchAsync(controller.getMeasurementById));

export default router;
import cron from "node-cron";
import { MeasurementController } from "../controllers/MeasurementController";

/**
 * Singleton class for scheduling and managing cron jobs for measurements
 */
export default class CronScheduler {
  private static instance: CronScheduler;
  private task: cron.ScheduledTask | null = null;
  private minutesInterval: number = 0;
  private measurementController: MeasurementController;

  public nextScheduledDate: Date | null = null;

  /**
   * Private constructor to prevent direct instantiation
   */
  private constructor() {
    this.measurementController = new MeasurementController();
  }

  /**
   * Get the singleton instance of CronScheduler
   */
  public static getInstance(): CronScheduler {
    if (!CronScheduler.instance) {
      CronScheduler.instance = new CronScheduler();
    }
    return CronScheduler.instance;
  }

  /**
   * The job function that runs when the cron is triggered
   */
  private job = async (): Promise<void> => {
    const now = new Date();
    console.log(
      `Running automatic measurement at: ${now.toISOString()}, interval: ${
        this.minutesInterval
      } minutes`,
    );

    // Update the next scheduled date
    this.nextScheduledDate = new Date(
      now.getTime() + this.minutesInterval * 60 * 1000,
    );

    try {
      const result =
        await this.measurementController.startMeasurementLogic(true);
      console.log("Automatic measurement finished successfully");
      console.log(result.dataValues);
    } catch (error) {
      const err = error as Error;
      console.error(`Error in automatic measurement: ${err.message}`);
      console.error(err.stack);
    }
  };

  /**
   * Set a new schedule for measurements
   *
   * @param minutesInterval The interval between measurements in minutes
   * @param startTime The time to start the first measurement (defaults to now)
   */
  public setNewSchedule = (
    minutesInterval: number,
    startTime: Date = new Date(),
  ): void => {
    // Stop existing job if there is one
    if (this.task) {
      this.task.stop();
      this.task = null;
    }

    if (minutesInterval <= 0) {
      console.log("No automatic measurement scheduled - invalid interval");
      this.nextScheduledDate = null;
      return;
    }

    this.minutesInterval = minutesInterval;

    // Create cron expression
    let cronExpression: string;
    if (minutesInterval < 1) {
      // For sub-minute intervals (less common)
      const seconds = Math.floor(minutesInterval * 60);
      cronExpression = `*/${seconds} * * * * *`;
    } else {
      // For minute intervals (more common)
      cronExpression = `*/${minutesInterval} * * * *`;
    }

    // Calculate the delay until start time
    const now = new Date();
    const delay = startTime.getTime() - now.getTime();

    // Create the cron task
    const cronTask = cron.schedule(cronExpression, this.job, {
      scheduled: false, // Don't start immediately
      name: "measurement-task",
    });

    // If the start time is in the future, delay the start of the cron job
    if (delay > 0) {
      console.log(
        `Automatic measurement scheduled at: ${startTime.toISOString()}, interval: ${minutesInterval} minutes`,
      );
      this.nextScheduledDate = startTime;

      setTimeout(() => {
        this.task = cronTask;
        cronTask.start();
      }, delay);
    } else {
      console.log(`Next measurement in ${minutesInterval} minutes`);
      this.nextScheduledDate = new Date(
        now.getTime() + minutesInterval * 60 * 1000,
      );
      this.task = cronTask;
      cronTask.start();
    }
  };
}
