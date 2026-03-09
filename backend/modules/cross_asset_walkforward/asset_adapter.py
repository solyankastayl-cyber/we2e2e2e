"""
Asset Adapter Layer
===================

Normalizes behavior across different asset classes
without introducing asset-specific hacks in the core engine.
"""

from typing import Dict, Optional
from .types import (
    AssetAdapter, AssetClass, TradingCalendar, 
    ExecutionProfile
)


class AssetAdapterFactory:
    """
    Factory for creating asset-specific adapters.
    
    Each adapter provides:
    - Trading calendar (market hours vs 24/7)
    - Execution assumptions (fees, slippage)
    - Structural properties (bias, regime policy)
    - Self-healing calibration thresholds
    - Risk parameters
    """
    
    def __init__(self):
        self._adapters: Dict[str, AssetAdapter] = {}
        self._load_default_adapters()
    
    def _load_default_adapters(self):
        """Load default adapters for supported assets"""
        
        # ============================================
        # EQUITIES
        # ============================================
        
        # SPX - S&P 500 Index
        self.register(AssetAdapter(
            asset="SPX",
            asset_class=AssetClass.EQUITY,
            trading_calendar=TradingCalendar.DAILY_MARKET,
            allow_shorts=True,
            execution_profile=ExecutionProfile.EQUITY,
            default_fee_bps=5.0,
            default_slippage_bps=3.0,
            structural_bias_allowed=True,    # SPX has long-term long bias
            regime_policy_profile="equity_default",
            # Relaxed thresholds for equities (from Phase 9.3F fix)
            demote_winrate_threshold=0.30,
            promote_winrate_threshold=0.55,
            weight_decay_factor=0.95,
            weight_boost_factor=1.03,
            max_position_pct=0.15,
            max_drawdown_trigger=0.35
        ))
        
        # ============================================
        # CRYPTO
        # ============================================
        
        # BTC - Bitcoin
        self.register(AssetAdapter(
            asset="BTC",
            asset_class=AssetClass.CRYPTO,
            trading_calendar=TradingCalendar.CRYPTO_24_7,
            allow_shorts=True,
            execution_profile=ExecutionProfile.CRYPTO,
            default_fee_bps=10.0,
            default_slippage_bps=10.0,
            structural_bias_allowed=False,
            regime_policy_profile="crypto_default",
            # Standard crypto thresholds (more aggressive)
            demote_winrate_threshold=0.35,
            promote_winrate_threshold=0.60,
            weight_decay_factor=0.90,
            weight_boost_factor=1.05,
            max_position_pct=0.10,
            max_drawdown_trigger=0.40
        ))
        
        # ETH - Ethereum
        self.register(AssetAdapter(
            asset="ETH",
            asset_class=AssetClass.CRYPTO,
            trading_calendar=TradingCalendar.CRYPTO_24_7,
            allow_shorts=True,
            execution_profile=ExecutionProfile.CRYPTO,
            default_fee_bps=10.0,
            default_slippage_bps=12.0,
            structural_bias_allowed=False,
            regime_policy_profile="crypto_default",
            demote_winrate_threshold=0.35,
            promote_winrate_threshold=0.60,
            weight_decay_factor=0.90,
            weight_boost_factor=1.05,
            max_position_pct=0.10,
            max_drawdown_trigger=0.40
        ))
        
        # SOL - Solana
        self.register(AssetAdapter(
            asset="SOL",
            asset_class=AssetClass.CRYPTO,
            trading_calendar=TradingCalendar.CRYPTO_24_7,
            allow_shorts=True,
            execution_profile=ExecutionProfile.CRYPTO,
            default_fee_bps=15.0,
            default_slippage_bps=20.0,    # Higher slippage for altcoins
            structural_bias_allowed=False,
            regime_policy_profile="crypto_volatile",
            demote_winrate_threshold=0.35,
            promote_winrate_threshold=0.60,
            weight_decay_factor=0.88,      # More aggressive decay
            weight_boost_factor=1.06,
            max_position_pct=0.08,         # Lower position size
            max_drawdown_trigger=0.45
        ))
        
        # ============================================
        # FX
        # ============================================
        
        # DXY - US Dollar Index
        self.register(AssetAdapter(
            asset="DXY",
            asset_class=AssetClass.FX,
            trading_calendar=TradingCalendar.DAILY_MARKET,
            allow_shorts=True,
            execution_profile=ExecutionProfile.FX,
            default_fee_bps=3.0,
            default_slippage_bps=2.0,
            structural_bias_allowed=False,
            regime_policy_profile="fx_default",
            # FX thresholds (between equity and crypto)
            demote_winrate_threshold=0.32,
            promote_winrate_threshold=0.58,
            weight_decay_factor=0.92,
            weight_boost_factor=1.04,
            max_position_pct=0.12,
            max_drawdown_trigger=0.30
        ))
        
        # ============================================
        # COMMODITIES
        # ============================================
        
        # GOLD
        self.register(AssetAdapter(
            asset="GOLD",
            asset_class=AssetClass.COMMODITY,
            trading_calendar=TradingCalendar.DAILY_MARKET,
            allow_shorts=True,
            execution_profile=ExecutionProfile.COMMODITY,
            default_fee_bps=5.0,
            default_slippage_bps=5.0,
            structural_bias_allowed=False,
            regime_policy_profile="commodity_default",
            # Commodity thresholds
            demote_winrate_threshold=0.33,
            promote_winrate_threshold=0.57,
            weight_decay_factor=0.93,
            weight_boost_factor=1.04,
            max_position_pct=0.12,
            max_drawdown_trigger=0.35
        ))
    
    def register(self, adapter: AssetAdapter) -> None:
        """Register an asset adapter"""
        self._adapters[adapter.asset.upper()] = adapter
    
    def get(self, asset: str) -> Optional[AssetAdapter]:
        """Get adapter for an asset"""
        return self._adapters.get(asset.upper())
    
    def get_or_default(self, asset: str) -> AssetAdapter:
        """Get adapter or create default based on asset class"""
        adapter = self.get(asset)
        if adapter:
            return adapter
        
        # Create default adapter
        asset_upper = asset.upper()
        
        # Detect asset class
        if any(c in asset_upper for c in ["BTC", "ETH", "SOL", "XRP", "ADA"]):
            asset_class = AssetClass.CRYPTO
        elif any(e in asset_upper for e in ["SPX", "SPY", "NDX", "QQQ"]):
            asset_class = AssetClass.EQUITY
        elif any(f in asset_upper for f in ["DXY", "EUR", "GBP", "JPY"]):
            asset_class = AssetClass.FX
        elif any(c in asset_upper for c in ["GOLD", "XAU", "SILVER", "OIL"]):
            asset_class = AssetClass.COMMODITY
        else:
            asset_class = AssetClass.UNKNOWN
        
        return self._create_default_adapter(asset, asset_class)
    
    def _create_default_adapter(self, asset: str, asset_class: AssetClass) -> AssetAdapter:
        """Create default adapter based on asset class"""
        
        if asset_class == AssetClass.CRYPTO:
            return AssetAdapter(
                asset=asset,
                asset_class=AssetClass.CRYPTO,
                trading_calendar=TradingCalendar.CRYPTO_24_7,
                execution_profile=ExecutionProfile.CRYPTO,
                default_fee_bps=10.0,
                default_slippage_bps=15.0,
                demote_winrate_threshold=0.35,
                promote_winrate_threshold=0.60
            )
        
        elif asset_class == AssetClass.EQUITY:
            return AssetAdapter(
                asset=asset,
                asset_class=AssetClass.EQUITY,
                trading_calendar=TradingCalendar.DAILY_MARKET,
                execution_profile=ExecutionProfile.EQUITY,
                default_fee_bps=5.0,
                default_slippage_bps=3.0,
                structural_bias_allowed=True,
                demote_winrate_threshold=0.30,
                promote_winrate_threshold=0.55
            )
        
        elif asset_class == AssetClass.FX:
            return AssetAdapter(
                asset=asset,
                asset_class=AssetClass.FX,
                trading_calendar=TradingCalendar.DAILY_MARKET,
                execution_profile=ExecutionProfile.FX,
                default_fee_bps=3.0,
                default_slippage_bps=2.0,
                demote_winrate_threshold=0.32,
                promote_winrate_threshold=0.58
            )
        
        elif asset_class == AssetClass.COMMODITY:
            return AssetAdapter(
                asset=asset,
                asset_class=AssetClass.COMMODITY,
                trading_calendar=TradingCalendar.DAILY_MARKET,
                execution_profile=ExecutionProfile.COMMODITY,
                default_fee_bps=5.0,
                default_slippage_bps=5.0,
                demote_winrate_threshold=0.33,
                promote_winrate_threshold=0.57
            )
        
        # Default unknown
        return AssetAdapter(
            asset=asset,
            asset_class=AssetClass.UNKNOWN,
            trading_calendar=TradingCalendar.DAILY_MARKET,
            execution_profile=ExecutionProfile.EQUITY
        )
    
    def list_assets(self) -> list:
        """List all registered assets"""
        return list(self._adapters.keys())
    
    def list_by_class(self, asset_class: AssetClass) -> list:
        """List assets by class"""
        return [
            asset for asset, adapter in self._adapters.items()
            if adapter.asset_class == asset_class
        ]
    
    def to_dict(self) -> dict:
        """Export as dictionary"""
        return {
            asset: {
                "asset": adapter.asset,
                "asset_class": adapter.asset_class.value,
                "trading_calendar": adapter.trading_calendar.value,
                "allow_shorts": adapter.allow_shorts,
                "structural_bias_allowed": adapter.structural_bias_allowed,
                "default_fee_bps": adapter.default_fee_bps,
                "default_slippage_bps": adapter.default_slippage_bps,
                "demote_winrate_threshold": adapter.demote_winrate_threshold,
                "promote_winrate_threshold": adapter.promote_winrate_threshold
            }
            for asset, adapter in self._adapters.items()
        }


# Singleton instance
asset_adapter_factory = AssetAdapterFactory()
