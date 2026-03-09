"""
Binance Broker Adapter
======================

Adapter for Binance Spot and Futures trading.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import hashlib
import hmac
import time
import httpx

from .base_adapter import (
    BaseBrokerAdapter,
    BrokerCredentials,
    BrokerStatus,
    OrderSide,
    OrderType,
    OrderStatus,
    TimeInForce,
    Order,
    Position,
    Balance,
    Ticker,
    ConnectionError,
    AuthenticationError,
    OrderError,
    InsufficientFundsError,
    RateLimitError
)


class BinanceAdapter(BaseBrokerAdapter):
    """
    Binance broker adapter.
    
    Supports:
    - Spot trading
    - Futures trading (USDT-M)
    - Market data
    """
    
    # API Endpoints
    SPOT_BASE_URL = "https://api.binance.com"
    SPOT_TESTNET_URL = "https://testnet.binance.vision"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
    
    def __init__(self, credentials: BrokerCredentials, use_futures: bool = False):
        super().__init__(credentials)
        self.use_futures = use_futures
        self._client: Optional[httpx.AsyncClient] = None
        
        # Set base URL
        if use_futures:
            self._base_url = self.FUTURES_TESTNET_URL if credentials.testnet else self.FUTURES_BASE_URL
        else:
            self._base_url = self.SPOT_TESTNET_URL if credentials.testnet else self.SPOT_BASE_URL
    
    @property
    def broker_name(self) -> str:
        return "binance_futures" if self.use_futures else "binance_spot"
    
    @property
    def supports_futures(self) -> bool:
        return self.use_futures
    
    @property
    def supports_margin(self) -> bool:
        return True
    
    def _sign(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.credentials.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers"""
        return {
            "X-MBX-APIKEY": self.credentials.api_key,
            "Content-Type": "application/json"
        }
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make API request"""
        self._increment_request_count()
        
        if not self._client:
            raise ConnectionError("Not connected. Call connect() first.")
        
        params = params or {}
        
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._sign(params)
        
        url = f"{self._base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self._client.get(url, params=params, headers=self._get_headers())
            elif method == "POST":
                response = await self._client.post(url, params=params, headers=self._get_headers())
            elif method == "DELETE":
                response = await self._client.delete(url, params=params, headers=self._get_headers())
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Check for errors
            if response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            
            data = response.json()
            
            if response.status_code >= 400:
                error_code = data.get("code", "UNKNOWN")
                error_msg = data.get("msg", "Unknown error")
                
                if error_code in [-2010, -2011]:  # Insufficient balance
                    raise InsufficientFundsError(error_msg, str(error_code))
                elif error_code in [-2013, -2014]:  # Order does not exist
                    raise OrderError(error_msg, str(error_code))
                elif error_code in [-1021, -1022]:  # Timestamp/signature issues
                    raise AuthenticationError(error_msg, str(error_code))
                else:
                    raise OrderError(error_msg, str(error_code))
            
            return data
            
        except httpx.RequestError as e:
            self.last_error = str(e)
            raise ConnectionError(f"Request failed: {e}")
    
    # ===========================================
    # Connection
    # ===========================================
    
    async def connect(self) -> bool:
        """Connect to Binance API"""
        self.status = BrokerStatus.CONNECTING
        
        try:
            self._client = httpx.AsyncClient(timeout=30.0)
            
            # Test connection with server time
            if self.use_futures:
                response = await self._client.get(f"{self._base_url}/fapi/v1/time")
            else:
                response = await self._client.get(f"{self._base_url}/api/v3/time")
            
            if response.status_code != 200:
                raise ConnectionError("Failed to connect to Binance API")
            
            # Verify API key by getting account info
            await self.get_balance()
            
            self.status = BrokerStatus.CONNECTED
            self.connected_at = datetime.now(timezone.utc)
            return True
            
        except Exception as e:
            self.status = BrokerStatus.ERROR
            self.last_error = str(e)
            raise
    
    async def disconnect(self) -> bool:
        """Disconnect from Binance"""
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self.status = BrokerStatus.DISCONNECTED
        self.connected_at = None
        return True
    
    async def is_connected(self) -> bool:
        """Check connection status"""
        return self.status == BrokerStatus.CONNECTED and self._client is not None
    
    # ===========================================
    # Account
    # ===========================================
    
    async def get_balance(self, asset: Optional[str] = None) -> List[Balance]:
        """Get account balances"""
        if self.use_futures:
            endpoint = "/fapi/v2/balance"
        else:
            endpoint = "/api/v3/account"
        
        data = await self._request("GET", endpoint, signed=True)
        
        balances = []
        
        if self.use_futures:
            # Futures response format
            for item in data:
                if asset and item["asset"] != asset:
                    continue
                
                free = float(item.get("availableBalance", 0))
                total = float(item.get("balance", 0))
                locked = total - free
                
                if total > 0 or asset:
                    balances.append(Balance(
                        asset=item["asset"],
                        free=free,
                        locked=locked,
                        total=total
                    ))
        else:
            # Spot response format
            for item in data.get("balances", []):
                if asset and item["asset"] != asset:
                    continue
                
                free = float(item["free"])
                locked = float(item["locked"])
                
                if (free + locked) > 0 or asset:
                    balances.append(Balance(
                        asset=item["asset"],
                        free=free,
                        locked=locked
                    ))
        
        return balances
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get open positions (futures only)"""
        if not self.use_futures:
            return []
        
        endpoint = "/fapi/v2/positionRisk"
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        data = await self._request("GET", endpoint, params=params, signed=True)
        
        positions = []
        for item in data:
            size = float(item.get("positionAmt", 0))
            if size == 0:
                continue
            
            positions.append(Position(
                symbol=item["symbol"],
                side="LONG" if size > 0 else "SHORT",
                size=abs(size),
                entry_price=float(item.get("entryPrice", 0)),
                current_price=float(item.get("markPrice", 0)),
                unrealized_pnl=float(item.get("unRealizedProfit", 0)),
                leverage=float(item.get("leverage", 1)),
                liquidation_price=float(item.get("liquidationPrice", 0)) or None
            ))
        
        return positions
    
    # ===========================================
    # Market Data
    # ===========================================
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get ticker for symbol"""
        if self.use_futures:
            endpoint = "/fapi/v1/ticker/bookTicker"
        else:
            endpoint = "/api/v3/ticker/bookTicker"
        
        data = await self._request("GET", endpoint, params={"symbol": symbol})
        
        # Get 24h stats
        if self.use_futures:
            stats_endpoint = "/fapi/v1/ticker/24hr"
        else:
            stats_endpoint = "/api/v3/ticker/24hr"
        
        stats = await self._request("GET", stats_endpoint, params={"symbol": symbol})
        
        return Ticker(
            symbol=symbol,
            bid=float(data["bidPrice"]),
            ask=float(data["askPrice"]),
            last=float(stats["lastPrice"]),
            volume_24h=float(stats["quoteVolume"]),
            change_24h=float(stats["priceChangePercent"]) / 100,
            high_24h=float(stats["highPrice"]),
            low_24h=float(stats["lowPrice"])
        )
    
    async def get_tickers(self, symbols: Optional[List[str]] = None) -> List[Ticker]:
        """Get multiple tickers"""
        if self.use_futures:
            endpoint = "/fapi/v1/ticker/24hr"
        else:
            endpoint = "/api/v3/ticker/24hr"
        
        data = await self._request("GET", endpoint)
        
        tickers = []
        for item in data:
            if symbols and item["symbol"] not in symbols:
                continue
            
            tickers.append(Ticker(
                symbol=item["symbol"],
                bid=float(item.get("bidPrice", 0)),
                ask=float(item.get("askPrice", 0)),
                last=float(item["lastPrice"]),
                volume_24h=float(item["quoteVolume"]),
                change_24h=float(item["priceChangePercent"]) / 100,
                high_24h=float(item["highPrice"]),
                low_24h=float(item["lowPrice"])
            ))
        
        return tickers
    
    # ===========================================
    # Orders
    # ===========================================
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map internal order type to Binance format"""
        mapping = {
            OrderType.MARKET: "MARKET",
            OrderType.LIMIT: "LIMIT",
            OrderType.STOP_LOSS: "STOP_MARKET" if self.use_futures else "STOP_LOSS",
            OrderType.STOP_LIMIT: "STOP" if self.use_futures else "STOP_LOSS_LIMIT",
            OrderType.TAKE_PROFIT: "TAKE_PROFIT_MARKET" if self.use_futures else "TAKE_PROFIT",
            OrderType.TAKE_PROFIT_LIMIT: "TAKE_PROFIT" if self.use_futures else "TAKE_PROFIT_LIMIT"
        }
        return mapping.get(order_type, "MARKET")
    
    def _map_order_status(self, status: str) -> OrderStatus:
        """Map Binance order status to internal format"""
        mapping = {
            "NEW": OrderStatus.NEW,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED
        }
        return mapping.get(status, OrderStatus.NEW)
    
    def _parse_order(self, data: Dict[str, Any]) -> Order:
        """Parse Binance order response to Order object"""
        return Order(
            id=str(data.get("clientOrderId", data.get("orderId"))),
            broker_order_id=str(data["orderId"]),
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            order_type=OrderType(data["type"]) if data["type"] in [e.value for e in OrderType] else OrderType.MARKET,
            quantity=float(data.get("origQty", 0)),
            price=float(data.get("price", 0)) or None,
            stop_price=float(data.get("stopPrice", 0)) or None,
            time_in_force=TimeInForce(data.get("timeInForce", "GTC")),
            status=self._map_order_status(data["status"]),
            filled_quantity=float(data.get("executedQty", 0)),
            avg_fill_price=float(data.get("avgPrice", data.get("price", 0))),
            commission=0.0,  # Would need to fetch from trades
            created_at=datetime.fromtimestamp(data.get("time", 0) / 1000, tz=timezone.utc),
            updated_at=datetime.fromtimestamp(data.get("updateTime", data.get("time", 0)) / 1000, tz=timezone.utc)
        )
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Place order on Binance"""
        if self.use_futures:
            endpoint = "/fapi/v1/order"
        else:
            endpoint = "/api/v3/order"
        
        params = {
            "symbol": symbol,
            "side": side.value,
            "type": self._map_order_type(order_type),
            "quantity": str(quantity)
        }
        
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        
        if order_type != OrderType.MARKET:
            params["timeInForce"] = time_in_force.value
        
        if price and order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
            params["price"] = str(price)
        
        if stop_price and order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT]:
            params["stopPrice"] = str(stop_price)
        
        data = await self._request("POST", endpoint, params=params, signed=True)
        
        return self._parse_order(data)
    
    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Cancel order on Binance"""
        if self.use_futures:
            endpoint = "/fapi/v1/order"
        else:
            endpoint = "/api/v3/order"
        
        params = {"symbol": symbol}
        
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        else:
            raise OrderError("Either order_id or client_order_id required")
        
        data = await self._request("DELETE", endpoint, params=params, signed=True)
        
        return self._parse_order(data)
    
    async def get_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        client_order_id: Optional[str] = None
    ) -> Order:
        """Get order from Binance"""
        if self.use_futures:
            endpoint = "/fapi/v1/order"
        else:
            endpoint = "/api/v3/order"
        
        params = {"symbol": symbol}
        
        if order_id:
            params["orderId"] = order_id
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        else:
            raise OrderError("Either order_id or client_order_id required")
        
        data = await self._request("GET", endpoint, params=params, signed=True)
        
        return self._parse_order(data)
    
    async def get_orders(
        self,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders from Binance"""
        if self.use_futures:
            endpoint = "/fapi/v1/allOrders" if status else "/fapi/v1/openOrders"
        else:
            endpoint = "/api/v3/allOrders" if status else "/api/v3/openOrders"
        
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        
        data = await self._request("GET", endpoint, params=params, signed=True)
        
        orders = [self._parse_order(item) for item in data]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Cancel all open orders"""
        if not symbol:
            raise OrderError("Symbol required for cancel_all_orders on Binance")
        
        if self.use_futures:
            endpoint = "/fapi/v1/allOpenOrders"
        else:
            endpoint = "/api/v3/openOrders"
        
        params = {"symbol": symbol}
        
        data = await self._request("DELETE", endpoint, params=params, signed=True)
        
        if isinstance(data, list):
            return [self._parse_order(item) for item in data]
        return []
