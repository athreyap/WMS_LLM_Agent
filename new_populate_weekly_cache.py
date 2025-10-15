def populate_weekly_and_monthly_cache(self, user_id):
    """
    TICKER-WISE INCREMENTAL weekly price cache update:
    - Process ONE ticker at a time (fetch all weeks, save all at once)
    - Only fetches NEW weeks since last cache update
    - Automatically triggered during login
    - Weekly data saved to historical_prices table
    - Includes AI fallback for failed MF codes
    - Includes CAGR calculation for PMS/AIF
    """
    from datetime import datetime, timedelta
    import yfinance as yf
    
    try:
        # Get transactions for the user
        transactions = get_transactions_supabase(user_id)
        if not transactions:
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(transactions)
        df['date'] = pd.to_datetime(df['date'])
        
        # Get unique tickers
        unique_tickers = df['ticker'].unique()
        
        current_date = datetime.now()
        one_year_ago = current_date - timedelta(days=365)
        
        st.info(f"🔄 Checking weekly prices for {len(unique_tickers)} tickers...")
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_saved = 0
        total_skipped = 0
        
        # Process each ticker individually
        for ticker_idx, ticker in enumerate(unique_tickers):
            try:
                ticker_str = str(ticker).strip()
                stock_name = df[df['ticker'] == ticker]['stock_name'].iloc[0]
                
                # Update progress
                progress = (ticker_idx + 1) / len(unique_tickers)
                progress_bar.progress(progress)
                status_text.text(f"📊 Processing {ticker_idx + 1}/{len(unique_tickers)}: {ticker_str}...")
                
                # Detect asset type
                is_pms_aif = (ticker_str.startswith('INP') or ticker_str.startswith('INA') or 
                             'PMS' in ticker_str.upper() or 'AIF' in ticker_str.upper())
                is_bse = (ticker_str.isdigit() and len(ticker_str) == 6 and ticker_str.startswith('5'))
                is_mutual_fund = ((ticker_str.isdigit() and len(ticker_str) in [5, 6] and not is_bse) or 
                                ticker_str.startswith('MF_'))
                
                # STEP 1: Get max cached date for THIS ticker using direct query
                max_date_query = supabase.table('historical_prices')\
                    .select('transaction_date')\
                    .eq('ticker', ticker_str)\
                    .order('transaction_date', desc=True)\
                    .limit(1)\
                    .execute()
                
                if max_date_query.data and len(max_date_query.data) > 0:
                    max_cached_str = max_date_query.data[0]['transaction_date']
                    max_cached = pd.to_datetime(max_cached_str)
                    start_from = max_cached + timedelta(days=7)  # Start from next week
                else:
                    start_from = one_year_ago  # No cache, fetch full year
                
                # Check if up to date
                if start_from >= current_date:
                    print(f"✅ {ticker_str}: Already up to date")
                    total_skipped += 1
                    continue
                
                # STEP 2: Fetch ALL missing weeks for this ticker in ONE call
                weekly_prices_to_save = []
                
                if is_pms_aif:
                    # PMS/AIF: Calculate using CAGR
                    print(f"💼 {ticker_str}: PMS/AIF - calculating CAGR...")
                    
                    trans_data = df[df['ticker'] == ticker].iloc[0]
                    trans_date = pd.to_datetime(trans_data['date'])
                    trans_price = float(trans_data['price'])
                    quantity = float(trans_data['quantity'])
                    
                    # Fetch current NAV via AI
                    try:
                        from ai_price_fetcher import AIPriceFetcher
                        ai_fetcher = AIPriceFetcher()
                        
                        # Get current NAV
                        current_result = ai_fetcher.get_pms_aif_performance(ticker_str, stock_name)
                        
                        if current_result and 'current_nav' in current_result:
                            current_nav = float(current_result['current_nav'])
                            
                            # Calculate CAGR
                            years = (current_date - trans_date).days / 365.25
                            if years > 0:
                                cagr = ((current_nav / trans_price) ** (1/years)) - 1
                                
                                # Generate weekly NAVs
                                weekly_dates = pd.date_range(start=start_from, end=current_date, freq='W-MON')
                                
                                for week_date in weekly_dates:
                                    years_from_start = (week_date - trans_date).days / 365.25
                                    if years_from_start >= 0:
                                        weekly_nav = trans_price * ((1 + cagr) ** years_from_start)
                                        weekly_prices_to_save.append({
                                            'ticker': ticker_str,
                                            'date': week_date.strftime('%Y-%m-%d'),
                                            'price': float(weekly_nav),
                                            'source': 'pms_cagr'
                                        })
                                
                                print(f"✅ {ticker_str}: CAGR = {cagr*100:.2f}%, {len(weekly_prices_to_save)} weeks generated")
                        else:
                            print(f"⚠️ {ticker_str}: Could not fetch current NAV via AI")
                    
                    except Exception as e:
                        print(f"❌ {ticker_str}: CAGR calculation failed - {e}")
                
                elif is_mutual_fund:
                    # MF: Try mftool first, then AI fallback
                    print(f"📊 {ticker_str}: Mutual Fund - fetching weekly NAVs...")
                    
                    # Get current NAV
                    try:
                        from mf_price_fetcher import MFPriceFetcher
                        mf_fetcher = MFPriceFetcher()
                        scheme_code = int(ticker_str.replace('MF_', ''))
                        
                        nav_data = mf_fetcher.get_mutual_fund_nav(scheme_code)
                        
                        if nav_data and nav_data.get('nav', 0) > 0:
                            current_nav = float(nav_data['nav'])
                            
                            # For MF, just save current NAV (weekly data not available historically)
                            weekly_prices_to_save.append({
                                'ticker': ticker_str,
                                'date': current_date.strftime('%Y-%m-%d'),
                                'price': current_nav,
                                'source': 'mftool_current'
                            })
                            print(f"✅ {ticker_str}: mftool NAV = ₹{current_nav}")
                        else:
                            # AI fallback
                            from ai_price_fetcher import AIPriceFetcher
                            ai_fetcher = AIPriceFetcher()
                            
                            ai_result = ai_fetcher.get_mutual_fund_nav(
                                ticker_str, 
                                stock_name, 
                                current_date.strftime('%Y-%m-%d')
                            )
                            
                            if ai_result and ai_result.get('price', 0) > 0:
                                current_nav = float(ai_result['price'])
                                weekly_prices_to_save.append({
                                    'ticker': ticker_str,
                                    'date': current_date.strftime('%Y-%m-%d'),
                                    'price': current_nav,
                                    'source': 'ai_mf'
                                })
                                print(f"🤖 {ticker_str}: AI NAV = ₹{current_nav}")
                    
                    except Exception as e:
                        print(f"⚠️ {ticker_str}: MF fetch failed - {e}")
                
                else:
                    # Stock: Fetch ALL missing weeks in ONE yfinance call
                    print(f"📈 {ticker_str}: Stock - fetching {(current_date - start_from).days // 7} weeks...")
                    
                    try:
                        # Try NSE first
                        yf_ticker = f"{ticker_str}.NS"
                        stock = yf.Ticker(yf_ticker)
                        hist = stock.history(start=start_from, end=current_date, interval='1wk')
                        
                        if hist.empty:
                            # Try BSE
                            yf_ticker = f"{ticker_str}.BO"
                            stock = yf.Ticker(yf_ticker)
                            hist = stock.history(start=start_from, end=current_date, interval='1wk')
                        
                        if not hist.empty:
                            for date_idx, price in zip(hist.index, hist['Close']):
                                if pd.notna(price) and not np.isinf(price) and price > 0:
                                    weekly_prices_to_save.append({
                                        'ticker': ticker_str,
                                        'date': date_idx.strftime('%Y-%m-%d'),
                                        'price': float(price),
                                        'source': 'yfinance_weekly'
                                    })
                            
                            print(f"✅ {ticker_str}: yfinance = {len(hist)} weeks")
                        else:
                            print(f"⚠️ {ticker_str}: No data from yfinance")
                    
                    except Exception as e:
                        print(f"⚠️ {ticker_str}: yfinance failed - {e}")
                
                # STEP 3: Bulk save all weeks for THIS ticker
                if weekly_prices_to_save:
                    try:
                        bulk_save_historical_prices(weekly_prices_to_save)
                        total_saved += len(weekly_prices_to_save)
                        print(f"💾 {ticker_str}: Saved {len(weekly_prices_to_save)} weekly prices")
                    except Exception as e:
                        print(f"❌ {ticker_str}: Save failed - {e}")
                
            except Exception as ticker_error:
                print(f"❌ Error processing ticker {ticker}: {ticker_error}")
                continue
        
        # Complete
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        
        st.success(f"✅ Weekly cache complete: {total_saved} prices saved, {total_skipped} tickers up-to-date")
        
    except Exception as e:
        st.error(f"❌ Error in weekly cache: {e}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

