# PMS/AIF CAGR-Based Price Calculation

## ✅ Changes Implemented

### 1. **Always Fetch Prices (Ignore CSV Price Column)**
- **Location:** `process_csv_file()` - Line 696-698
- **Change:** Now ALWAYS fetches prices, ignoring any price values in the CSV
- **Reason:** Ensures accurate, real-time pricing instead of relying on potentially outdated CSV data

```python
# ✅ ALWAYS fetch prices (ignore CSV price column)
st.info(f"🔍 Fetching prices for ALL transactions in {uploaded_file.name}...")
df = self.fetch_historical_prices_for_transactions(df)
```

---

### 2. **PMS/AIF: Invested Amount → CAGR → Historical NAVs**
- **Location:** `fetch_historical_prices_for_transactions()` - Lines 804-870
- **Logic:**

#### **Step 1: Calculate Transaction Price**
```python
# Get invested amount from CSV (or calculate from price × quantity)
invested_amount = row.get('invested_amount', 0) or row.get('amount', 0)
if not invested_amount or invested_amount <= 0:
    csv_price = row.get('price', 0)
    quantity = row.get('quantity', 1)
    if csv_price and csv_price > 0:
        invested_amount = csv_price * quantity

# Calculate per-unit price
transaction_price = invested_amount / quantity
```

#### **Step 2: Fetch Current NAV from AI**
```python
# Get current NAV using AI
current_nav_result = ai_fetcher.get_pms_aif_nav(ticker, stock_name)  # No date = current
current_nav = current_nav_result['price']
```

#### **Step 3: Calculate CAGR**
```python
# CAGR formula: ((Current/Initial)^(1/years)) - 1
days_elapsed = (today - transaction_date).days
years_elapsed = days_elapsed / 365.25

cagr = ((current_nav / transaction_price) ** (1 / years_elapsed)) - 1
```

#### **Step 4: Store CAGR for Future Use**
```python
# Store CAGR and current NAV in DataFrame
df.at[idx, 'cagr'] = cagr
df.at[idx, 'current_nav'] = current_nav
```

**This CAGR is saved to the transactions table for future calculations!**

---

### 3. **Historical Price Calculation Using CAGR**
- **Location:** `fetch_historical_price_comprehensive()` - Lines 1413-1468
- **Logic:**

```python
# Get transaction data (includes CAGR)
transaction_price = float(latest_txn['price'])
transaction_date = pd.to_datetime(latest_txn['date'])
cagr = latest_txn.get('cagr', None)

if cagr and pd.notna(cagr):
    # Calculate NAV for target date using CAGR
    days_diff = (target_date - transaction_date).days
    years_diff = days_diff / 365.25
    
    # NAV at target date = Transaction NAV × (1 + CAGR)^years
    calculated_nav = transaction_price * ((1 + float(cagr)) ** years_diff)
    
    print(f"✅ Calculated NAV using CAGR ({float(cagr)*100:.2f}%) = ₹{calculated_nav:.2f}")
else:
    # No CAGR available, use transaction price
    calculated_nav = transaction_price
```

---

## 📊 **Example Scenario**

### **File Upload: `buoyant_pms.csv`**

| ticker | stock_name | quantity | invested_amount | date |
|--------|------------|----------|----------------|------|
| INP000005000 | Buoyant Opportunities | 1 | 7,000,000 | 2024-01-06 |

### **Processing Flow:**

#### **1. Calculate Transaction Price**
```
Transaction Price = 7,000,000 / 1 = ₹7,000,000 per unit
```

#### **2. Fetch Current NAV (AI)**
```
🤖 AI: Current NAV = ₹8,500,000 (as of Oct 2024)
```

#### **3. Calculate CAGR**
```
Days: (2024-10-14) - (2024-01-06) = 282 days
Years: 282 / 365.25 = 0.77 years

CAGR = ((8,500,000 / 7,000,000)^(1/0.77)) - 1
     = (1.214^1.30) - 1
     = 0.285 (28.5% annualized return)
```

#### **4. Store in Database**
```sql
INSERT INTO transactions (
    ticker, price, quantity, cagr, current_nav, ...
) VALUES (
    'INP000005000', 7000000, 1, 0.285, 8500000, ...
)
```

---

### **Weekly/Historical Price Calculation**

When fetching weekly prices for portfolio analysis:

```python
# Example: Calculate NAV on 2024-07-01 (6 months after purchase)

transaction_date = 2024-01-06
target_date = 2024-07-01
transaction_nav = 7,000,000
cagr = 0.285

days_diff = (2024-07-01) - (2024-01-06) = 176 days
years_diff = 176 / 365.25 = 0.48 years

NAV on 2024-07-01 = 7,000,000 × (1 + 0.285)^0.48
                  = 7,000,000 × 1.13
                  = ₹7,910,000

✅ This is now stored in historical_prices table!
```

---

## 🎯 **Benefits**

1. ✅ **Accurate PMS/AIF Tracking**: Uses invested amount, not arbitrary prices
2. ✅ **CAGR-Based Growth**: Realistic NAV calculation based on actual performance
3. ✅ **Historical Reconstruction**: Can calculate any past NAV using CAGR
4. ✅ **API First for Stocks/MFs**: Free APIs used where possible, AI as fallback
5. ✅ **Consistent Data**: All prices fetched fresh, not dependent on CSV quality

---

## 🔄 **Asset Type Strategy**

| Asset Type | Price Fetching Strategy |
|------------|------------------------|
| **Stocks** | 1. Try yfinance API (FREE)<br>2. Fallback to AI |
| **Mutual Funds** | 1. Try mftool API (FREE)<br>2. Fallback to AI |
| **PMS/AIF** | 1. Use invested amount<br>2. Fetch current NAV via AI<br>3. Calculate CAGR<br>4. Use CAGR for all historical/weekly NAVs |

---

## 📝 **Database Schema Update Required**

To support CAGR storage, ensure the `transactions` table has these columns:

```sql
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS cagr FLOAT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS current_nav FLOAT;
```

These columns will be populated automatically during CSV processing for PMS/AIF transactions.

---

## 🚀 **Next Steps**

1. **Deploy Changes**: Push to GitHub and deploy to Streamlit Cloud
2. **Test Upload**: Upload a PMS/AIF CSV file
3. **Verify CAGR**: Check that CAGR is calculated and stored correctly
4. **Check Weekly Prices**: Verify that weekly/historical NAVs are calculated using CAGR

---

## ✅ **Verification**

**File Compiled:** ✅ No syntax errors
**Location:** `web_agent.py`
**Lines Modified:**
- 696-698: Always fetch prices
- 804-870: PMS/AIF CAGR calculation
- 1413-1468: Historical NAV calculation using CAGR

