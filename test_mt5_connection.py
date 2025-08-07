from mt5_connector import MT5Connector
import time

def test_mt5_connection():
    """Simple test to verify MT5 connectivity and AutoTrading status"""
    # Initialize the connector
    mt5_conn = MT5Connector(
        symbol="EURUSD",
        timeframe="M5",
        lot_size=0.01,
        backtest_timeframe=100
    )
    
    # Check if MT5 is initialized
    if mt5_conn.initialize():
        print("✅ MT5 initialized successfully")
    else:
        print("❌ MT5 initialization failed")
        return
    
    # Check if AutoTrading is enabled
    can_trade, message = mt5_conn.can_trade()
    print(f"AutoTrading status: {message}")
    
    # Test placing a dummy order (with volume=0 so it won't actually execute)
    # This will show if AutoTrading is enabled
    print("Testing SELL order (with zero volume):")
    mt5_conn.test_order_permissions()
    
    # Clean up
    mt5_conn.shutdown()
    print("MT5 connection test completed")

if __name__ == "__main__":
    test_mt5_connection()