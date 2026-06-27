import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# पेज कॉन्फ़िगरेशन
st.set_page_config(
    page_title="📊 Trading Backtest Dashboard",
    page_icon="📈",
    layout="wide"
)

# टाइटल
st.title("📊 स्टॉक ट्रेडिंग बैकटेस्टिंग डैशबोर्ड")
st.markdown("---")

# साइडबार
with st.sidebar:
    st.header("⚙️ सेटिंग्स")
    
    symbol = st.text_input("📌 स्टॉक सिंबल", value="AAPL").upper()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("शुरुआत", datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("अंत", datetime.now())
    
    st.subheader("📈 SMA पैरामीटर्स")
    sma_short = st.number_input("Short SMA", value=50, min_value=5, max_value=200, step=5)
    sma_long = st.number_input("Long SMA", value=200, min_value=20, max_value=300, step=5)
    
    initial_capital = st.number_input("💰 कैपिटल ($)", value=10000, min_value=1000, step=1000)
    
    run_btn = st.button("🚀 बैकटेस्ट चलाएं", type="primary", use_container_width=True)

# फंक्शन्स
@st.cache_data
def fetch_data(symbol, start, end):
    try:
        df = yf.download(symbol, start=start, end=end, progress=False)
        if df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"❌ एरर: {e}")
        return None

def calculate_indicators(df, short, long):
    df['SMA_Short'] = df['Close'].rolling(window=short).mean()
    df['SMA_Long'] = df['Close'].rolling(window=long).mean()
    return df

def generate_signals(df):
    df['Signal'] = 0
    df.loc[df['SMA_Short'] > df['SMA_Long'], 'Signal'] = 1
    df.loc[df['SMA_Short'] < df['SMA_Long'], 'Signal'] = -1
    df['Position'] = df['Signal'].diff()
    return df

def calculate_metrics(df):
    if df.empty or len(df) < 2:
        return None
    
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Returns'] * df['Signal'].shift(1)
    df['Cumulative'] = (1 + df['Strategy_Returns']).cumprod()
    
    total_return = (df['Cumulative'].iloc[-1] - 1) * 100 if not df['Cumulative'].isna().all() else 0
    
    if df['Strategy_Returns'].std() != 0 and len(df['Strategy_Returns'].dropna()) > 1:
        sharpe = (df['Strategy_Returns'].mean() / df['Strategy_Returns'].std()) * np.sqrt(252)
    else:
        sharpe = 0
    
    cumulative = df['Cumulative']
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max * 100
    max_dd = drawdown.min() if not drawdown.isna().all() else 0
    
    win_trades = df[df['Strategy_Returns'] > 0]['Strategy_Returns'].count()
    total_trades = df[df['Strategy_Returns'] != 0]['Strategy_Returns'].count()
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'total_return': total_return,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'win_rate': win_rate,
        'total_trades': total_trades
    }

def plot_chart(df, symbol, short, long):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1,
                        row_heights=[0.7, 0.3])
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='Price'
    ), row=1, col=1)
    
    # SMA
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Short'], 
                            line=dict(color='orange', width=2), 
                            name=f'SMA {short}'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Long'], 
                            line=dict(color='blue', width=2), 
                            name=f'SMA {long}'), row=1, col=1)
    
    # Signals
    buy = df[df['Position'] == 2]
    sell = df[df['Position'] == -2]
    
    fig.add_trace(go.Scatter(x=buy.index, y=buy['Close'],
                            mode='markers', marker=dict(symbol='triangle-up', 
                            size=15, color='green'), name='Buy'), row=1, col=1)
    fig.add_trace(go.Scatter(x=sell.index, y=sell['Close'],
                            mode='markers', marker=dict(symbol='triangle-down', 
                            size=15, color='red'), name='Sell'), row=1, col=1)
    
    # Volume
    colors = ['green' if row['Close'] >= row['Open'] else 'red' for _, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], 
                        marker_color=colors, name='Volume'), row=2, col=1)
    
    fig.update_layout(height=700, template='plotly_dark', hovermode='x unified')
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_yaxes(title_text='Price ($)', row=1, col=1)
    fig.update_yaxes(title_text='Volume', row=2, col=1)
    
    return fig

# ✅ मुख्य लॉजिक
if run_btn:
    if not symbol:
        st.warning("⚠️ कृपया स्टॉक सिंबल डालें!")
    elif start_date >= end_date:
        st.warning("⚠️ शुरुआत तारीख अंत से पहले होनी चाहिए!")
    else:
        with st.spinner('📥 डेटा लोड हो रहा है...'):
            df = fetch_data(symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            df = calculate_indicators(df, sma_short, sma_long)
            df = generate_signals(df)
            metrics = calculate_metrics(df)
            
            if metrics:
                # Metrics Cards
                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("📈 कुल रिटर्न", f"{metrics['total_return']:.2f}%")
                col2.metric("⚡ शार्प रेश्यो", f"{metrics['sharpe_ratio']:.2f}")
                col3.metric("📉 मैक्स ड्रॉडाउन", f"{metrics['max_drawdown']:.2f}%")
                col4.metric("🎯 जीत दर", f"{metrics['win_rate']:.1f}%")
                col5.metric("🔄 कुल ट्रेड्स", f"{metrics['total_trades']}")
                
                # Chart
                st.plotly_chart(plot_chart(df, symbol, sma_short, sma_long), 
                               use_container_width=True)
                
                # Data Table
                with st.expander("📋 डेटा देखें"):
                    st.dataframe(df.tail(30))
                
                # Download
                csv = df.to_csv().encode('utf-8')
                st.download_button("📥 CSV डाउनलोड करें", data=csv,
                                  file_name=f"{symbol}_data.csv", mime="text/csv")
        else:
            st.error(f"❌ {symbol} के लिए डेटा नहीं मिला! सही सिंबल डालें (जैसे AAPL, TSLA, RELIANCE.NS)")

# Footer
st.markdown("---")
st.caption("🚀 Streamlit + yfinance के साथ बनाया गया")