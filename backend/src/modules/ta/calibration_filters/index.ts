/**
 * Phase 8.6 — Calibration Filters Module Export
 */

export type {
  CalibrationFilterConfig,
  CalibrationFilterInput,
  CalibrationFilterResult,
  CandleWithVolume,
  CalibrationFilterReason,
} from './calibration_filters.types.js';

export {
  DEFAULT_CALIBRATION_FILTER_CONFIG,
} from './calibration_filters.types.js';

export {
  applyCalibrationFilters,
  isStrategyDisabled,
  getAdjustedLevels,
  filterScenarios,
} from './calibration_filters.engine.js';
