// Quick test for batch runner logic
import { mulberry32, generateCandles, makeDecision } from './runner.js';

const candles = generateCandles('BTCUSDT', '1d', 1640995200000, 1672531200000, 50, 42);
console.log('Generated candles:', candles.length);

let decisions = 0;
for (let i = 50; i < candles.length; i++) {
  const decision = makeDecision(candles, i);
  if (decision && decision.shouldTrade) {
    decisions++;
    console.log(`Decision at bar ${i}:`, decision.side, decision.patternType);
  }
}
console.log('Total decisions:', decisions);
