# MCX Silver Paper Trading System Guide

This system is a production-grade paper trading platform for MCX Silver Futures, utilizing a hybrid decision model that combines traditional rule-based technical analysis with Large Language Model (LLM) insights.

## How It Works

1.  **Data Ingestion**: The system connects to Angel One SmartAPI WebSocket to receive live tick data for MCX Silver futures.
2.  **Technical Analysis**: Every 30 seconds, it calculates various technical indicators:
    *   **RSI (Relative Strength Index)**: Identifies overbought/oversold conditions.
    *   **Moving Averages (MA 10, 20, 50)**: Determines trend direction and crossovers.
    *   **ATR (Average True Range)**: Measures volatility for dynamic stop-loss calculation.
    *   **Momentum Score**: A custom metric combining multiple factors.
3.  **Hybrid Decision Model**:
    *   **Rule-Based Filter**: Validates if the market conditions meet strict criteria (volatility, trend alignment, RSI limits).
    *   **LLM Analysis**: Sends the current market state and technical context to an LLM (via OpenRouter) for a final recommendation.
4.  **Risk Management**:
    *   **Dynamic Position Sizing**: Calculates lot size based on account equity and risk per trade.
    *   **Dynamic Stop Loss & Take Profit**: Sets levels based on ATR and support/resistance.
    *   **Trailing Stop Loss**: Automatically moves the stop loss in favor of the trade to lock in profits.

## Configuration

The system uses the `TRADING_CONFIG` dictionary for its behavior:

| Parameter | Default | Description |
| :--- | :--- | :--- |
| `starting_capital` | ₹500,000 | Initial virtual balance. |
| `max_position_risk_pct` | 1.5% | Max risk per single trade. |
| `min_risk_reward` | 2.0 | Minimum target-to-risk ratio. |
| `max_daily_trades` | 5 | Max number of trades per day. |
| `min_confidence_threshold`| 70% | Minimum LLM confidence to execute. |

## How to Run

1.  **Install Dependencies**:
    Ensure you have the required libraries installed:
    ```bash
    pip install SmartApi-python openai pandas numpy pyotp
    ```
2.  **Set Credentials**:
    The script has placeholders for Angel One API keys and OpenRouter API keys. You can update these directly in the script or modify it to use environment variables.
3.  **Execute**:
    Run the script using Python:
    ```bash
    python silver_trading_system.py
    ```
4.  **Follow Prompts**:
    *   Select the LLM model (GPT-4o mini, Claude 3.5, etc.).
    *   Enter starting capital and max daily trades.
    *   Press ENTER to start the live stream.

## Monitoring

The console will show:
*   Live tick data and current equity.
*   Hybrid analysis results every 30 seconds.
*   LLM reasoning and trade decisions.
*   Trade execution details (Entry, Stop Loss, Target).
*   Trailing stop updates.
*   Final session summary upon exit (Ctrl+C).

---
> [!IMPORTANT]
> This is a **Paper Trading System**. No real orders are placed on the exchange. It is intended for testing and refinement of trading strategies.
