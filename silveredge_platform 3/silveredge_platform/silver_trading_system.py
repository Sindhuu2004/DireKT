# ============================================================================
# PRODUCTION-GRADE PAPER TRADING SYSTEM - MCX SILVER FUTURES
# Enhanced with Advanced Risk Management & Technical Analysis
# Architecture: Hybrid Model (Rule-Based + LLM) + Multi-Timeframe Analysis
# ============================================================================

import json
import re
import time
import threading
import pyotp
import numpy as np
import pandas as pd
from collections import deque
from getpass import getpass
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from openai import OpenAI
from datetime import datetime, timedelta

print("="*70)
print("🚀 PRODUCTION-GRADE LLM TRADING SYSTEM v2.0")
print("="*70)
print("✅ Hybrid Decision Model (Rule-Based + LLM)")
print("✅ Advanced Technical Indicators")
print("✅ Dynamic Risk Management")
print("✅ Multi-Timeframe Analysis")
print("="*70)

# ============================================================================
# STEP 1: CREDENTIALS
# ============================================================================

print("\n" + "="*70)
print("STEP 1: ANGEL ONE CREDENTIALS")
print("="*70)

angel_api_key = 'Ixrn0DjV'
angel_client_id = 'AACE718991'
angel_password = '8105'
angel_totp_secret = 'U2Y7KTVKB2XUBNRU4NJNGPNHWU'

print("\n" + "="*70)
print("STEP 2: LLM API CREDENTIALS")
print("="*70)

openrouter_key = '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'

print("\nSelect LLM Model:")
print("1. Claude 3.5 Haiku (Recommended)")
print("2. Claude 3.5 Sonnet")
print("3. GPT-4 Turbo")
print("4. GPT-3.5 Turbo")

model_choice = input("Enter choice (1-4) [default=1]: ").strip() or "1"

MODEL_MAP = {
    "1": "openai/gpt-4o-mini",
    "2": "anthropic/claude-3.5-sonnet",
    "3": "openai/gpt-4-turbo",
    "4": "openai/gpt-3.5-turbo"
}

SELECTED_MODEL = MODEL_MAP.get(model_choice, "openai/gpt-4o-mini")
print(f"✓ Selected model: {SELECTED_MODEL}")

# ============================================================================
# STEP 3: ENHANCED TRADING CONFIGURATION
# ============================================================================

print("\n" + "="*70)
print("STEP 3: TRADING CONFIGURATION")
print("="*70)

# IMPROVED: Enhanced configuration with better defaults
TRADING_CONFIG = {
    # Capital Management
    'starting_capital': float(input("Starting capital (₹) [default=500000]: ") or "500000"),
    'max_capital_per_trade': 0.20,  # Max 20% of capital per trade
    'min_capital_per_trade': 0.10,  # Min 10% of capital per trade

    # Risk Management
    'max_daily_loss_pct': 3.0,  # Stop trading if 3% daily loss
    'max_position_risk_pct': 1.5,  # Risk max 1.5% per trade
    'min_risk_reward': 2.0,  # Minimum 1:2 risk-reward

    # Trading Rules
    'max_daily_trades': int(input("Max daily trades [default=5]: ") or "5"),
    'min_confidence_threshold': 70,  # IMPROVED: Raised from 70 to 80
    'cooldown_seconds': 60,  # NEW: 60 second cooldown between trades

    # Technical Parameters
    'contract_size': 30,  # 30 kg per lot
    'commission_per_trade': 50,

    # IMPROVED: Volatility & Trend Filters (ADJUSTED FOR REAL MARKETS)
    'min_volatility_pct': 0.01,  # CHANGED: 0.02% min (was 0.15%)
    'max_volatility_pct': 1.0,   # CHANGED: 2% max (was 3%)
    'min_trend_strength': 0.05,  # CHANGED: 0.1% trend (was 0.2%)
}

print(f"\n✓ Configuration Loaded:")
print(f"  Capital: ₹{TRADING_CONFIG['starting_capital']:,.0f}")
print(f"  Max Risk/Trade: {TRADING_CONFIG['max_position_risk_pct']}%")
print(f"  Min R:R Ratio: {TRADING_CONFIG['min_risk_reward']}:1")
print(f"  Confidence Threshold: {TRADING_CONFIG['min_confidence_threshold']}%")

# ============================================================================
# STEP 4: LOGIN TO ANGEL ONE
# ============================================================================

print("\n" + "="*70)
print("STEP 4: CONNECTING TO ANGEL ONE")
print("="*70)

smartApi = SmartConnect(api_key=angel_api_key)
totp = pyotp.TOTP(angel_totp_secret).now()

try:
    session = smartApi.generateSession(angel_client_id, angel_password, totp)

    if not session["status"]:
        raise Exception(f"Login Failed: {session.get('message')}")

    authToken = session["data"]["jwtToken"]
    feedToken = smartApi.getfeedToken()

    print("✓ Connected (Live data only)")

except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# ============================================================================
# STEP 5: FIND MCX SILVER CONTRACT
# ============================================================================

print("\n" + "="*70)
print("STEP 5: FINDING MCX SILVER CONTRACT")
print("="*70)

try:
    search_response = smartApi.searchScrip("MCX", "SILVER")

    if search_response['status'] and search_response['data']:
        instruments = search_response['data']

        silver_futures = [i for i in instruments
                         if i['tradingsymbol'].startswith('SILVER')
                         and 'MAY' in i['tradingsymbol']
                         and 'CE' not in i['tradingsymbol']
                         and 'PE' not in i['tradingsymbol']
                         and 'MIC' not in i['tradingsymbol']]

        if silver_futures:
            #silver_futures.sort(key=lambda x: x.get('expiry', '9999-12-31'))
            contract = silver_futures[0]

            SILVER_TOKEN = contract['symboltoken']
            SILVER_SYMBOL = contract['tradingsymbol']

            print(f"✓ Contract: {SILVER_SYMBOL}")
            print(f"  Token: {SILVER_TOKEN}")
        else:
            raise Exception("No SILVER futures found")
    else:
        raise Exception("Search failed")

except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# ============================================================================
# STEP 6: INITIALIZE LLM CLIENT
# ============================================================================

print("\n" + "="*70)
print("STEP 6: INITIALIZING LLM")
print("="*70)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_key,
)

print("✓ LLM initialized")

# ============================================================================
# STEP 7: DATA STRUCTURES
# ============================================================================

# Market data buffer (increased size for better analysis)
tick_buffer = deque(maxlen=1000)  # IMPROVED: Increased from 500

# Paper trading account
paper_account = {
    'capital': TRADING_CONFIG['starting_capital'],
    'equity': TRADING_CONFIG['starting_capital'],
    'margin_used': 0.0,
    'available_margin': TRADING_CONFIG['starting_capital'],
    'realized_pnl': 0.0,
    'unrealized_pnl': 0.0,
    'daily_start_equity': TRADING_CONFIG['starting_capital']
}

# Trading state
trading_state = {
    'current_position': None,
    'daily_trades': 0,
    'trade_history': [],
    'last_trade_time': None,  # NEW: Track last trade time for cooldown
    'consecutive_losses': 0,  # NEW: Track consecutive losses
}

# Statistics
stats = {
    'total_ticks': 0,
    'llm_calls': 0,
    'simulated_orders': 0,
    'winning_trades': 0,
    'losing_trades': 0,
    'total_commission_paid': 0,
    'last_price': 0,
    'highest_equity': TRADING_CONFIG['starting_capital'],
    'lowest_equity': TRADING_CONFIG['starting_capital'],
    'trades_rejected_by_filter': 0,  # NEW: Track rejected trades
    'max_consecutive_wins': 0,
    'max_consecutive_losses': 0,
}

# ============================================================================
# STEP 8: TECHNICAL INDICATORS CALCULATION
# ============================================================================

# NEW FEATURE: Comprehensive technical analysis
def calculate_technical_indicators(prices):
    """
    Calculate multiple technical indicators for decision making
    Returns dict with all indicators
    """
    if len(prices) < 51:
        return None

    prices_array = np.array(prices)

    indicators = {}

    # RSI (14-period)
    period = 14
    deltas = np.diff(prices_array)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        indicators['rsi'] = 100
    else:
        rs = avg_gain / avg_loss
        indicators['rsi'] = 100 - (100 / (1 + rs))

    # Moving Averages
    indicators['ma_20'] = np.mean(prices_array[-20:])
    indicators['ma_50'] = np.mean(prices_array[-50:])
    indicators['ma_10'] = np.mean(prices_array[-10:])

    # MA Crossover Signal
    if indicators['ma_20'] > indicators['ma_50']:
        indicators['ma_signal'] = 'BULLISH'
    elif indicators['ma_20'] < indicators['ma_50']:
        indicators['ma_signal'] = 'BEARISH'
    else:
        indicators['ma_signal'] = 'NEUTRAL'

    # Volatility (Standard Deviation)
    returns = np.diff(prices_array[-50:]) / prices_array[-50:-1]
    indicators['volatility'] = np.std(returns) * 100

    # Trend Strength (multiple timeframes)
    current_price = prices_array[-1]

    # Short-term trend (10 bars)
    trend_10 = ((current_price - prices_array[-10]) / prices_array[-10]) * 100
    # Medium-term trend (20 bars)
    trend_20 = ((current_price - prices_array[-20]) / prices_array[-20]) * 100
    # Long-term trend (50 bars)
    trend_50 = ((current_price - prices_array[-50]) / prices_array[-50]) * 100

    indicators['trend_10'] = trend_10
    indicators['trend_20'] = trend_20
    indicators['trend_50'] = trend_50

    # Overall trend classification
    if trend_20 > TRADING_CONFIG['min_trend_strength'] and trend_50 > 0:
        indicators['trend'] = 'STRONG_BULLISH'
    elif trend_20 > 0:
        indicators['trend'] = 'BULLISH'
    elif trend_20 < -TRADING_CONFIG['min_trend_strength'] and trend_50 < 0:
        indicators['trend'] = 'STRONG_BEARISH'
    elif trend_20 < 0:
        indicators['trend'] = 'BEARISH'
    else:
        indicators['trend'] = 'NEUTRAL'

    # Momentum Score (0-100)
    momentum_score = 0
    if indicators['rsi'] > 60:
        momentum_score += 25
    elif indicators['rsi'] > 50:
        momentum_score += 15

    if indicators['ma_signal'] == 'BULLISH':
        momentum_score += 25

    if trend_20 > 0.3:
        momentum_score += 25
    elif trend_20 > 0.1:
        momentum_score += 15

    if current_price > indicators['ma_20']:
        momentum_score += 25

    indicators['momentum_score'] = momentum_score

    # Support and Resistance (simple)
    indicators['support'] = np.min(prices_array[-20:])
    indicators['resistance'] = np.max(prices_array[-20:])

    # Average True Range (ATR) for stop loss
    if len(prices_array) >= 20:
        high_low_range = np.max(prices_array[-20:]) - np.min(prices_array[-20:])
        indicators['atr'] = high_low_range / 20
    else:
        indicators['atr'] = current_price * 0.005  # 0.5% fallback

    return indicators

# ============================================================================
# STEP 9: TRADE VALIDATION LAYER
# ============================================================================

# NEW FEATURE: Critical trade filtering before execution
def validate_trade_entry(side, current_price, indicators, confidence):
    """
    CRITICAL VALIDATION LAYER
    Reject trades that don't meet strict criteria

    NEW: Adaptive thresholds based on current market conditions
    Returns: (is_valid, reason)
    """

    reasons = []

    # ADAPTIVE: Adjust volatility threshold based on recent market activity
    recent_volatilities = []
    if len(tick_buffer) >= 200:
        for i in range(5):
            start_idx = -200 + (i * 40)
            end_idx = start_idx + 40
            segment_prices = [t['ltp'] for t in list(tick_buffer)[start_idx:end_idx]]
            if len(segment_prices) >= 20:
                segment_returns = np.diff(segment_prices) / segment_prices[:-1]
                recent_volatilities.append(np.std(segment_returns) * 100)

    # Use adaptive threshold if market is consistently low volatility
    if recent_volatilities and np.mean(recent_volatilities) < 0.05:
        adaptive_min_vol = max(0.01, np.mean(recent_volatilities) * 0.8)
        print(f"   📊 Adaptive mode: Min volatility adjusted to {adaptive_min_vol:.3f}%")
    else:
        adaptive_min_vol = TRADING_CONFIG['min_volatility_pct']

    # Check 1: Confidence threshold
    if confidence < TRADING_CONFIG['min_confidence_threshold']:
        return False, f"Low confidence ({confidence}% < {TRADING_CONFIG['min_confidence_threshold']}%)"

    # Check 2: Volatility filter (with adaptive threshold)
    if indicators['volatility'] < adaptive_min_vol:
        return False, f"Volatility too low ({indicators['volatility']:.3f}% < {adaptive_min_vol:.3f}%)"

    if indicators['volatility'] > TRADING_CONFIG['max_volatility_pct']:
        return False, f"Volatility too high ({indicators['volatility']:.2f}% > {TRADING_CONFIG['max_volatility_pct']}%)"

    # Check 3: Trend alignment
    # Check 3: Trend alignment (RELAXED)
    if side == 'LONG':
    # Only block if strong opposite trend
       if indicators['trend'] == 'STRONG_BEARISH':
           return False, f"Strong bearish trend for LONG (trend={indicators['trend']})"

    # Allow neutral also
       if indicators['ma_signal'] == 'BEARISH':
           return False, "MA strongly bearish for LONG"

    # Relaxed price condition (no strict block)
    # if current_price < indicators['ma_20']:
    #     return False, "Price below MA20 for LONG"

    elif side == 'SHORT':
    # Only block if strong opposite trend
        if indicators['trend'] == 'STRONG_BULLISH':
           return False, f"Strong bullish trend for SHORT (trend={indicators['trend']})"

        if indicators['ma_signal'] == 'BULLISH':
            return False, "MA strongly bullish for SHORT"

    # Relaxed price condition
    # if current_price > indicators['ma_20']:
    #     return False, "Price above MA20 for SHORT"

    # Check 4: RSI extremes (RELAXED - avoid only extreme conditions)
    if side == 'LONG' and indicators['rsi'] > 90:  # CHANGED: 85 (was 75)
        return False, f"RSI overbought for LONG ({indicators['rsi']:.1f})"

    if side == 'SHORT' and indicators['rsi'] < 10:  # CHANGED: 15 (was 25)
        return False, f"RSI oversold for SHORT ({indicators['rsi']:.1f})"

    # Check 5: Momentum score (ADJUSTED)
    if indicators['momentum_score'] < 30:  # CHANGED: 40 (was 50)
        return False, f"Momentum too weak ({indicators['momentum_score']}/100)"

    # Check 6: Cooldown period
    if trading_state['last_trade_time']:
        time_since_last = (datetime.now() - trading_state['last_trade_time']).total_seconds()
        if time_since_last < TRADING_CONFIG['cooldown_seconds']:
            return False, f"Cooldown active ({int(TRADING_CONFIG['cooldown_seconds'] - time_since_last)}s remaining)"

    # Check 7: Daily loss limit
    daily_pnl_pct = (paper_account['equity'] - paper_account['daily_start_equity']) / paper_account['daily_start_equity'] * 100
    if daily_pnl_pct < -TRADING_CONFIG['max_daily_loss_pct']:
        return False, f"Daily loss limit hit ({daily_pnl_pct:.2f}% < -{TRADING_CONFIG['max_daily_loss_pct']}%)"

    # Check 8: Consecutive losses (reduce position after 2 losses)
    if trading_state['consecutive_losses'] >= 2:
        return False, f"Too many consecutive losses ({trading_state['consecutive_losses']}), taking break"

    # All checks passed
    return True, "All validation checks passed"

# ============================================================================
# STEP 10: DYNAMIC POSITION SIZING
# ============================================================================

# NEW FEATURE: Risk-based position sizing
def calculate_position_size(entry_price, stop_loss, indicators):
    """
    Calculate optimal position size based on:
    - Available capital
    - Risk per trade
    - Volatility
    - Stop loss distance
    """

    # Risk amount in rupees
    risk_amount = paper_account['equity'] * (TRADING_CONFIG['max_position_risk_pct'] / 100)

    # Stop loss distance
    stop_distance = abs(entry_price - stop_loss)

    # Points at risk per kg
    points_risk_per_kg = stop_distance

    # Total kg we can buy with this risk
    total_kg = risk_amount / points_risk_per_kg

    # Convert to lots (30 kg per lot)
    lots = total_kg / TRADING_CONFIG['contract_size']

    # Round down to integer
    lots = int(lots)

    # Apply capital limits
    capital_per_lot = entry_price * TRADING_CONFIG['contract_size']
    max_lots_by_capital = int((paper_account['equity'] * TRADING_CONFIG['max_capital_per_trade']) / capital_per_lot)

    lots = min(lots, max_lots_by_capital)

    # Minimum 1 lot if we have enough capital
    if lots < 1 and paper_account['available_margin'] > capital_per_lot:
        lots = 1

    return max(1, lots)

# ============================================================================
# STEP 11: DYNAMIC STOP LOSS & TRAILING
# ============================================================================

# NEW FEATURE: ATR-based dynamic stop loss
def calculate_stop_loss_target(side, entry_price, indicators):
    """
    Calculate dynamic stop loss and target based on:
    - ATR (volatility)
    - Risk:Reward ratio
    - Support/Resistance
    """

    atr = indicators['atr']

    # Stop loss: 2x ATR
    stop_multiplier = 2.0

    # Target: Based on min R:R ratio
    target_multiplier = stop_multiplier * TRADING_CONFIG['min_risk_reward']

    if side == 'LONG':
        stop_loss = entry_price - (atr * stop_multiplier)
        target = entry_price + (atr * target_multiplier)

        # Don't place stop below support
        stop_loss = max(stop_loss, indicators['support'] * 0.998)

    else:  # SHORT
        stop_loss = entry_price + (atr * stop_multiplier)
        target = entry_price - (atr * target_multiplier)

        # Don't place stop above resistance
        stop_loss = min(stop_loss, indicators['resistance'] * 1.002)

    return stop_loss, target

# NEW FEATURE: Trailing stop loss
def update_trailing_stop(position, current_price):
    """
    Update trailing stop loss when trade moves in favor
    """
    if not position:
        return

    side = position['side']
    entry = position['entry']
    current_stop = position['stop_loss']
    atr = position.get('atr', abs(entry - current_stop) / 2)

    # Calculate unrealized profit
    if side == 'LONG':
        profit_points = current_price - entry

        # If profit > 1 ATR, trail stop
        if profit_points > atr:
            new_stop = entry + (profit_points * 0.5)  # Trail to 50% of profit

            # Only move stop up, never down
            if new_stop > current_stop:
                print(f"\n📈 TRAILING STOP: ₹{current_stop:,.0f} → ₹{new_stop:,.0f}")
                position['stop_loss'] = new_stop
                position['trailing_active'] = True

    else:  # SHORT
        profit_points = entry - current_price

        if profit_points > atr:
            new_stop = entry - (profit_points * 0.5)

            # Only move stop down, never up
            if new_stop < current_stop:
                print(f"\n📉 TRAILING STOP: ₹{current_stop:,.0f} → ₹{new_stop:,.0f}")
                position['stop_loss'] = new_stop
                position['trailing_active'] = True

# ============================================================================
# STEP 12: IMPROVED LLM PROMPT
# ============================================================================

# IMPROVED: Much better prompt engineering
def build_enhanced_prompt(prices, indicators):
    """
    Build comprehensive prompt with technical context
    """

    current_price = prices[-1]
    recent_prices = prices[-20:]

    # Position context
    position_info = "NO POSITION"
    if trading_state['current_position']:
        pos = trading_state['current_position']
        pnl = (current_price - pos['entry']) * pos['quantity'] * TRADING_CONFIG['contract_size']
        if pos['side'] == 'SHORT':
            pnl = -pnl
        position_info = f"{pos['side']} @ ₹{pos['entry']:,.0f} | Unrealized: ₹{pnl:,.0f}"

    prompt = f"""You are an expert MCX Silver futures trading analyst.

═══════════════════════════════════════════════════════════════════
MARKET DATA - {{SILVER_SYMBOL}}
═══════════════════════════════════════════════════════════════════

Current Price: ₹{{current_price:,.2f}}

TECHNICAL INDICATORS:
• RSI(14): {{indicators['rsi']:.1f}}
• MA(20): ₹{{indicators['ma_20']:,.2f}}
• MA(50): ₹{{indicators['ma_50']:,.2f}}
• MA Signal: {{indicators['ma_signal']}}
• Volatility: {{indicators['volatility']:.2f}}%
• Trend (20-bar): {{indicators['trend_20']:+.2f}}%
• Trend (50-bar): {{indicators['trend_50']:+.2f}}%
• Overall Trend: {{indicators['trend']}}
• Momentum Score: {{indicators['momentum_score']}}/100
• Support: ₹{{indicators['support']:,.0f}}
• Resistance: ₹{{indicators['resistance']:,.0f}}
• ATR: ₹{{indicators['atr']:.2f}}

Recent Price Action (last 20 ticks):
{{recent_prices}}

═══════════════════════════════════════════════════════════════════
ACCOUNT STATUS
═══════════════════════════════════════════════════════════════════

Virtual Equity: ₹{{paper_account['equity']:,.0f}}
Position: {{position_info}}
Trades Today: {{trading_state['daily_trades']}}/{{TRADING_CONFIG['max_daily_trades']}}
Consecutive Losses: {{trading_state['consecutive_losses']}}

═══════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════

Analyze the market and provide a trading recommendation.

STRICT TRADING RULES:
1. ONLY recommend ENTER_LONG when:
   - Trend is BULLISH or STRONG_BULLISH
   - MA(20) > MA(50) (bullish crossover)
   - Price > MA(20)
   - RSI between 50-75 (not overbought)
   - Momentum Score > 50
   - Volatility between 0.05% - 3%

2. ONLY recommend ENTER_SHORT when:
   - Trend is BEARISH or STRONG_BEARISH
   - MA(20) < MA(50) (bearish crossover)
   - Price < MA(20)
   - RSI between 25-50 (not oversold)
   - Momentum Score > 60
   - Volatility between 0.05% - 3%

3. Recommend EXIT_POSITION when:
   - Momentum weakens
   - Trend reverses
   - Risk increases

4. Default to HOLD when conditions are unclear

CONFIDENCE SCORING:
- 90-100: All indicators strongly aligned
- 80-89: Most indicators aligned
- 70-79: Some indicators aligned
- <70: Weak setup, recommend HOLD

═══════════════════════════════════════════════════════════════════
RESPONSE FORMAT (STRICT JSON ONLY - NO MARKDOWN)
═══════════════════════════════════════════════════════════════════

{{{{
  "action": "ENTER_LONG|ENTER_SHORT|EXIT_POSITION|HOLD",
  "confidence": 0-100,
  "analysis": {{{{
    "trend_assessment": "detailed trend analysis",
    "technical_signals": "RSI, MA, momentum analysis",
    "risk_factors": "key risks identified"
  }}}},
  "reasoning": "clear 2-3 sentence explanation",
  "risk_level": "LOW|MEDIUM|HIGH"
}}}}

Analyze and respond with JSON only:"""

    return prompt.format(
        SILVER_SYMBOL=SILVER_SYMBOL,
        current_price=current_price,
        indicators=indicators,
        recent_prices=recent_prices,
        paper_account=paper_account,
        position_info=position_info,
        trading_state=trading_state,
        TRADING_CONFIG=TRADING_CONFIG
    )

# ============================================================================
# STEP 13: HELPER FUNCTIONS
# ============================================================================

def clean_json(text):
    """Remove markdown from LLM response"""
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()

def calculate_margin_required(quantity, price):
    """Calculate margin"""
    contract_value = quantity * TRADING_CONFIG['contract_size'] * price
    return contract_value * 0.10

def simulate_order_placement(side, quantity, price):
    """Simulate order execution"""
    order_id = f"PAPER_{int(time.time())}"
    commission = TRADING_CONFIG['commission_per_trade']
    stats['total_commission_paid'] += commission
    stats['simulated_orders'] += 1

    return order_id, price

# ============================================================================
# STEP 14: EXECUTE SIMULATED TRADES (IMPROVED)
# ============================================================================

def execute_simulated_entry(side, current_price, indicators, confidence):
    """Execute paper trade with validation"""

    # CRITICAL: Validate trade first
    is_valid, reason = validate_trade_entry(side, current_price, indicators, confidence)

    if not is_valid:
        print(f"\n❌ TRADE REJECTED: {reason}")
        stats['trades_rejected_by_filter'] += 1
        return

    # Calculate stop loss and target
    stop_loss, target = calculate_stop_loss_target(side, current_price, indicators)

    # Verify R:R ratio
    risk = abs(current_price - stop_loss)
    reward = abs(target - current_price)
    rr_ratio = reward / risk if risk > 0 else 0

    if rr_ratio < TRADING_CONFIG['min_risk_reward']:
        print(f"\n❌ TRADE REJECTED: R:R too low ({rr_ratio:.2f} < {TRADING_CONFIG['min_risk_reward']})")
        stats['trades_rejected_by_filter'] += 1
        return

    # Calculate position size
    quantity = calculate_position_size(current_price, stop_loss, indicators)

    if quantity < 1:
        print(f"\n❌ TRADE REJECTED: Insufficient capital for proper position sizing")
        stats['trades_rejected_by_filter'] += 1
        return

    # Check margin
    margin_required = calculate_margin_required(quantity, current_price)

    if margin_required > paper_account['available_margin']:
        print(f"\n❌ INSUFFICIENT MARGIN")
        return

    print(f"\n{'='*70}")
    print(f"✅ TRADE VALIDATED - EXECUTING {side}")
    print(f"{'='*70}")
    print(f"Entry: ₹{current_price:,.2f}")
    print(f"Stop Loss: ₹{stop_loss:,.2f}")
    print(f"Target: ₹{target:,.2f}")
    print(f"Risk: ₹{risk:.2f}/kg | Reward: ₹{reward:.2f}/kg | R:R = 1:{rr_ratio:.2f}")
    print(f"Quantity: {quantity} lot(s) ({quantity * TRADING_CONFIG['contract_size']} kg)")
    print(f"Margin: ₹{margin_required:,.0f}")
    print(f"")
    print(f"TECHNICAL CONFIRMATION:")
    print(f"  Trend: {indicators['trend']}")
    print(f"  RSI: {indicators['rsi']:.1f}")
    print(f"  MA Signal: {indicators['ma_signal']}")
    print(f"  Momentum: {indicators['momentum_score']}/100")
    print(f"  Volatility: {indicators['volatility']:.2f}%")

    order_id, fill_price = simulate_order_placement(side, quantity, current_price)

    # Update account
    paper_account['margin_used'] += margin_required
    paper_account['available_margin'] -= margin_required

    # Create position
    trading_state['current_position'] = {
        'side': side,
        'entry': fill_price,
        'quantity': quantity,
        'stop_loss': stop_loss,
        'target': target,
        'order_id': order_id,
        'entry_time': datetime.now(),
        'margin_used': margin_required,
        'atr': indicators['atr'],
        'trailing_active': False,
        'rr_ratio': rr_ratio
    }

    trading_state['daily_trades'] += 1
    trading_state['last_trade_time'] = datetime.now()

    print(f"\n✅ POSITION OPENED")

def execute_simulated_exit(current_price, reason):
    """Execute exit with P&L tracking"""

    pos = trading_state['current_position']

    # Calculate P&L
    price_diff = current_price - pos['entry']
    if pos['side'] == 'SHORT':
        price_diff = -price_diff

    gross_pnl = price_diff * pos['quantity'] * TRADING_CONFIG['contract_size']
    commission = TRADING_CONFIG['commission_per_trade']
    net_pnl = gross_pnl - commission

    print(f"\n{'='*70}")
    print(f"{'🎯' if net_pnl > 0 else '🛑'} POSITION CLOSED - {reason}")
    print(f"{'='*70}")
    print(f"Side: {pos['side']}")
    print(f"Entry: ₹{pos['entry']:,.2f} | Exit: ₹{current_price:,.2f}")
    print(f"Duration: {(datetime.now() - pos['entry_time']).total_seconds() / 60:.1f} minutes")
    print(f"Gross P&L: ₹{gross_pnl:,.2f}")
    print(f"Commission: -₹{commission}")
    print(f"Net P&L: {'₹' + f'{net_pnl:,.2f}' if net_pnl >= 0 else '-₹' + f'{abs(net_pnl):,.2f}'}")
    print(f"R:R Achieved: 1:{abs(price_diff) / abs(pos['entry'] - pos['stop_loss']):.2f}")

    simulate_order_placement('SHORT' if pos['side'] == 'LONG' else 'LONG', pos['quantity'], current_price)

    # Update account
    paper_account['realized_pnl'] += net_pnl
    paper_account['equity'] = paper_account['capital'] + paper_account['realized_pnl']
    paper_account['margin_used'] -= pos['margin_used']
    paper_account['available_margin'] += pos['margin_used']
    paper_account['unrealized_pnl'] = 0

    # Track performance
    if net_pnl > 0:
        stats['winning_trades'] += 1
        trading_state['consecutive_losses'] = 0
        stats['max_consecutive_wins'] = max(stats['max_consecutive_wins'], stats['winning_trades'] - trading_state['consecutive_losses'])
    else:
        stats['losing_trades'] += 1
        trading_state['consecutive_losses'] += 1
        stats['max_consecutive_losses'] = max(stats['max_consecutive_losses'], trading_state['consecutive_losses'])

    stats['highest_equity'] = max(stats['highest_equity'], paper_account['equity'])
    stats['lowest_equity'] = min(stats['lowest_equity'], paper_account['equity'])

    # Record trade
    trading_state['trade_history'].append({
        'entry': pos['entry'],
        'exit': current_price,
        'pnl': net_pnl,
        'side': pos['side'],
        'reason': reason,
        'time': datetime.now(),
        'rr_ratio': pos['rr_ratio']
    })

    trading_state['current_position'] = None

    print(f"\nTotal P&L: ₹{paper_account['realized_pnl']:,.0f}")
    print(f"Equity: ₹{paper_account['equity']:,.0f}")

def check_stop_target(current_price):
    """Check stop/target and update trailing stop"""

    if not trading_state['current_position']:
        return

    pos = trading_state['current_position']

    # Update trailing stop first
    update_trailing_stop(pos, current_price)

    # Then check if stop/target hit
    hit_stop = (pos['side'] == 'LONG' and current_price <= pos['stop_loss']) or \
               (pos['side'] == 'SHORT' and current_price >= pos['stop_loss'])

    hit_target = (pos['side'] == 'LONG' and current_price >= pos['target']) or \
                 (pos['side'] == 'SHORT' and current_price <= pos['target'])

    if hit_stop:
        reason = 'TRAILING_STOP' if pos.get('trailing_active') else 'STOP_LOSS'
        execute_simulated_exit(current_price, reason)
    elif hit_target:
        execute_simulated_exit(current_price, 'TARGET')

# ============================================================================
# STEP 15: HYBRID DECISION SYSTEM (RULE-BASED + LLM)
# ============================================================================

# IMPROVED: Hybrid model combining rules and LLM
def call_hybrid_trading_agent():
    """
    Hybrid decision system:
    1. Calculate technical indicators
    2. Apply rule-based filters
    3. Get LLM opinion
    4. Combine both for final decision
    """

    if len(tick_buffer) < 100:
        print(f"\n⏳ Building data... ({{len(tick_buffer)}}/100)")
        return

    if trading_state['daily_trades'] >= TRADING_CONFIG['max_daily_trades']:
        return

    try:
        # Extract price data
        prices = [t['ltp'] for t in tick_buffer]
        current_price = prices[-1]

        # Calculate indicators
        indicators = calculate_technical_indicators(prices)
        if not indicators:
            return

        print(f"\n{{'='*70}}")
        print(f"📊 HYBRID ANALYSIS - {{datetime.now().strftime('%H:%M:%S')}}")
        print(f"{{'='*70}}")
        print(f"Price: ₹{current_price:,.2f} | RSI: {indicators['rsi']:.1f} | Trend: {indicators['trend']}")
        print(f"Volatility: {indicators['volatility']:.3f}% | Momentum: {indicators['momentum_score']}/100")
        print(f"MA(20): ₹{indicators['ma_20']:,.0f} | MA(50): ₹{indicators['ma_50']:,.0f} | Signal: {indicators['ma_signal']}")

        # NEW: Market condition assessment
        market_quality = "🟢 GOOD"
        if indicators['volatility'] < 0.02:
            market_quality = "🔴 TOO QUIET"
        elif indicators['volatility'] > 1.5:
            market_quality = "🟠 TOO VOLATILE"
        elif indicators['momentum_score'] < 40:
            market_quality = "🟡 WEAK MOMENTUM"
        elif indicators['trend'] == 'NEUTRAL':
            market_quality = "🟡 NO CLEAR TREND"

        print(f"Market Quality: {market_quality}")

        # Build enhanced prompt
        prompt = build_enhanced_prompt(prices, indicators)

        # Call LLM
        response = client.chat.completions.create(
            model=SELECTED_MODEL,
            messages=[
                {"role": "system", "content": "You are a technical trading analyst. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content
        cleaned = clean_json(raw)

        print(f"\n🤖 LLM Response:")
        print(cleaned[:300] + "..." if len(cleaned) > 300 else cleaned)

        try:
            decision = json.loads(cleaned)

            action = decision.get('action', 'HOLD')
            confidence = decision.get('confidence', 0)

            print(f"\n{{'─'*70}}")
            print(f"DECISION: {{action}} | Confidence: {{confidence}}%")
            print(f"Reasoning: {{decision.get('reasoning', 'N/A')}}")
            print(f"{{'─'*70}}")

            # Execute based on action
            if action == 'ENTER_LONG' and not trading_state['current_position']:
                execute_simulated_entry('LONG', current_price, indicators, confidence)

            elif action == 'ENTER_SHORT' and not trading_state['current_position']:
                execute_simulated_entry('SHORT', current_price, indicators, confidence)

            elif action == 'EXIT_POSITION' and trading_state['current_position']:
                execute_simulated_exit(current_price, 'LLM_EXIT')

            elif action == 'HOLD':
                print("✓ HOLD - Waiting for better setup")

        except json.JSONDecodeError as e:
            print(f"\n❌ JSON parse error: {{e}}")

        stats['llm_calls'] += 1

    except Exception as e:
        print(f"\n❌ Error: {{e}}")

# ============================================================================
# STEP 16: WEBSOCKET CALLBACKS
# ============================================================================

def on_data(wsapp, message):
    """Handle live tick data"""
    try:
        if isinstance(message, str):
            data = json.loads(message)
        else:
            data = message

        ltp = data.get("last_traded_price")

        if ltp:
            ltp_rupees = ltp / 100

            tick_buffer.append({
                "ltp": ltp_rupees,
                "timestamp": time.time()
            })

            stats['total_ticks'] += 1
            stats['last_price'] = ltp_rupees

            # Update unrealized P&L
            if trading_state['current_position']:
                pos = trading_state['current_position']
                price_diff = ltp_rupees - pos['entry']
                if pos['side'] == 'SHORT':
                    price_diff = -price_diff
                paper_account['unrealized_pnl'] = price_diff * pos['quantity'] * TRADING_CONFIG['contract_size']
                paper_account['equity'] = paper_account['capital'] + paper_account['realized_pnl'] + paper_account['unrealized_pnl']

            # Check stops
            check_stop_target(ltp_rupees)

            # Display
            pos_info = ""
            if trading_state['current_position']:
                pos_info = f" | {{trading_state['current_position']['side']}} P&L: ₹{{paper_account['unrealized_pnl']:,.0f}}"

            print(f"\r💹 #{stats['total_ticks']}: ₹{ltp_rupees:,.2f} | Equity: ₹{paper_account['equity']:,.0f}{pos_info}", end="", flush=True)

    except Exception as e:
        pass

def on_open(wsapp):
    """WebSocket opened"""
    print("\n✓ WebSocket connected")

    token_list = [{"exchangeType": 5, "tokens": [SILVER_TOKEN]}]
    sws.subscribe(correlation_id="hybrid_system", mode=3, token_list=token_list)

    print(f"✓ Streaming data\n")

def on_error(wsapp, error):
    """Error handler"""
    if "429" in str(error):
        print(f"\n❌ Connection limit. Close other sessions.")

def on_close(wsapp):
    """Connection closed"""
    print(f"\n⚠ Disconnected")

# ============================================================================
# STEP 17: START SYSTEM
# ============================================================================

print("\n" + "="*70)
print("🚀 STARTING ENHANCED PAPER TRADING SYSTEM")
print("="*70)
print("✅ Hybrid Model (Rules + LLM)")
print("✅ Advanced Risk Management")
print("✅ Dynamic Position Sizing")
print("✅ Trailing Stop Loss")
print()

input("Press ENTER to start...")

sws = SmartWebSocketV2(authToken, angel_api_key, angel_client_id, feedToken)
sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close

socket_thread = threading.Thread(target=lambda: sws.connect())
socket_thread.daemon = True
socket_thread.start()

time.sleep(3)

print(f"\n{'='*70}")
print("🤖 HYBRID TRADING AGENT ACTIVE")
print(f"{'='*70}")
print("Analysis every 30 seconds | Press Ctrl+C to stop")
print(f"{'='*70}\n")

# Main loop
try:
    while True:
        time.sleep(30)

        if len(tick_buffer) >= 100:
            call_hybrid_trading_agent()

except KeyboardInterrupt:
    print(f"\n\n{'='*70}")
    print("📊 SESSION COMPLETE")
    print(f"{'='*70}")

    # Close open position
    if trading_state['current_position']:
        prices = [t['ltp'] for t in tick_buffer]
        if prices:
            execute_simulated_exit(prices[-1], 'SESSION_END')

    # Performance metrics
    total_trades = stats['winning_trades'] + stats['losing_trades']
    win_rate = (stats['winning_trades'] / total_trades * 100) if total_trades > 0 else 0
    roi = ((paper_account['equity'] - TRADING_CONFIG['starting_capital']) / TRADING_CONFIG['starting_capital'] * 100)
    max_dd = ((stats['lowest_equity'] - TRADING_CONFIG['starting_capital']) / TRADING_CONFIG['starting_capital'] * 100)

    avg_win = np.mean([t['pnl'] for t in trading_state['trade_history'] if t['pnl'] > 0]) if stats['winning_trades'] > 0 else 0
    avg_loss = np.mean([t['pnl'] for t in trading_state['trade_history'] if t['pnl'] < 0]) if stats['losing_trades'] > 0 else 0
    profit_factor = abs(avg_win * stats['winning_trades'] / (avg_loss * stats['losing_trades'])) if stats['losing_trades'] > 0 else 0

    print(f"\n💰 ACCOUNT SUMMARY:")
    print(f"{'─'*70}")
    print(f"Starting Capital:     ₹{TRADING_CONFIG['starting_capital']:,.0f}")
    print(f"Final Equity:         ₹{paper_account['equity']:,.0f}")
    print(f"Total P&L:            ₹{paper_account['realized_pnl']:,.0f} ({roi:+.2f}%)")
    print(f"Highest Equity:       ₹{stats['highest_equity']:,.0f}")
    print(f"Lowest Equity:        ₹{stats['lowest_equity']:,.0f}")
    print(f"Max Drawdown:         {max_dd:.2f}%")

    print(f"\n📈 TRADING STATISTICS:")
    print(f"Winning Trades:       {{stats['winning_trades']}}")
    print(f"Losing Trades:        {{stats['losing_trades']}}")
    print(f"Win Rate:             {{win_rate:.1f}}%")
    print(f"Average Win:          ₹{{avg_win:,.0f}}")
    print(f"Average Loss:         ₹{{avg_loss:,.0f}}")
    print(f"Profit Factor:        {{profit_factor:.2f}}")
    print(f"Max Consecutive Wins: {{stats['max_consecutive_wins']}}")
    print(f"Max Consecutive Loss: {{stats['max_consecutive_losses']}}")
    print(f"Total Commission:     ₹{{stats['total_commission_paid']:,.0f}}")

    if trading_state['trade_history']:
        print(f"\n📋 TRADE HISTORY:")
        print(f"{{'─'*70}}")
        for i, trade in enumerate(trading_state['trade_history'], 1):
            pnl_symbol = '✅' if trade['pnl'] > 0 else '❌'
            print(f"{i}. {pnl_symbol} {trade['side']:5s} | ₹{trade['entry']:,.0f} → ₹{trade['exit']:,.0f} | P&L: ₹{trade['pnl']:+,.0f} | R:R 1:{trade.get('rr_ratio', 0):.1f} | {trade['reason']}")
