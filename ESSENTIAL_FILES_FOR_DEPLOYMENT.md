# 📦 Essential Files for Deployment

## ✅ Core Application Files (REQUIRED)

### Main Application
- `web_agent.py` - Main Streamlit application ⭐

### Database & Configuration
- `database_config_supabase.py` - Database connection & queries ⭐
- `.streamlit/config.toml` - Streamlit configuration ⭐

### Price Fetching Modules
- `unified_price_fetcher.py` - Stock & MF price fetching ⭐
- `mf_price_fetcher.py` - Mutual fund NAV fetching
- `indstocks_api.py` - IndStocks API integration
- `pms_aif_fetcher.py` - PMS/AIF data fetching ⭐
- `pms_aif_updater.py` - PMS/AIF factsheet updates ⭐

### Dependencies
- `requirements.txt` - Python packages ⭐
- `.gitignore` - Git ignore rules
- `.stignore` - Streamlit ignore rules

### Documentation (Optional but recommended)
- `README.md` - Project documentation
- `README_SUPABASE.md` - Supabase setup guide

---

## ❌ Files to DELETE (Not needed for deployment)

### Test Files
- `test_*.py` - All test scripts
- `explore_*.py` - Exploration scripts
- `download_*.py` - Download scripts
- `sebi_*.py` - SEBI scraper attempts

### Documentation (Development only)
- `*_SUMMARY.md`
- `*_FIX.md`
- `*_GUIDE.md`
- `*_INSTRUCTIONS.md`
- `*_VERIFICATION.md`
- `*_EXPLANATION.md`
- `*_ENHANCEMENTS.md`
- `*_UPDATE.md`
- `PMS_AIF_INTEGRATION.md`
- `DATABASE_SCHEMA.md`
- `PROJECT_STATUS.md`
- `STREAMLIT_CLOUD_FIX.md`

### Setup Scripts (One-time use)
- `create_*.py`
- `setup_*.py`
- `add_*.py`
- `ensure_*.py`
- `install_*.py`

### SQL Files
- `*.sql`

### Unused Utilities
- `db_utils.py`
- `file_manager.py`
- `file_reading_agent.py`
- `user_file_reading_agent.py`
- `stock_data_agent.py`
- `smart_ticker_detector.py`
- `ticker_validator.py`
- `login_system.py`
- `optimized_data_loader.py`
- `sector_channel_clean.py`
- `fix_indentation.py`

### Data Directories (Empty them)
- `__pycache__/`
- `archive/`
- `csv_files/`
- `data/`
- `portfolio_data/`
- `transactions/`
- `investments/` (keep directory, delete contents)
- `kalyan/`
- `kalyan_files/`
- `test_admin_folder/`
- `test_user_folder/`
- `test_folder/`
- `test_no_channel/`
- `my_custom_folder/`

### CSV Files
- `*.csv` (All CSV files)

---

## 📋 Final File List (12 files only)

```
WMS-LLM/
├── .streamlit/
│   └── config.toml
├── .gitignore
├── .stignore
├── web_agent.py
├── database_config_supabase.py
├── unified_price_fetcher.py
├── mf_price_fetcher.py
├── indstocks_api.py
├── pms_aif_fetcher.py
├── pms_aif_updater.py
├── requirements.txt
├── README.md
└── README_SUPABASE.md
```

---

## 🚀 Deployment Steps

### 1. Clean Up Locally
```bash
# Delete all test files
Remove-Item test_*.py, explore_*.py, download_*.py, sebi_*.py -Force

# Delete all documentation except README
Remove-Item *_SUMMARY.md, *_FIX.md, *_GUIDE.md, *_INSTRUCTIONS.md -Force
Remove-Item *_VERIFICATION.md, *_EXPLANATION.md, *_ENHANCEMENTS.md -Force
Remove-Item PMS_AIF_INTEGRATION.md, DATABASE_SCHEMA.md, PROJECT_STATUS.md -Force

# Delete setup scripts
Remove-Item create_*.py, setup_*.py, add_*.py, ensure_*.py, install_*.py -Force

# Delete SQL files
Remove-Item *.sql -Force

# Delete unused utilities
Remove-Item db_utils.py, file_manager.py, *_agent.py, *_validator.py -Force
Remove-Item login_system.py, optimized_data_loader.py -Force

# Delete CSV files
Remove-Item *.csv -Force

# Delete data directories (or empty them)
Remove-Item -Recurse archive, csv_files, data, portfolio_data, transactions
Remove-Item -Recurse kalyan, kalyan_files, test_*_folder, my_custom_folder
```

### 2. Commit to Git
```bash
git add .
git commit -m "Clean: Remove unnecessary files for deployment"
git push origin main
```

### 3. Deploy to Streamlit Cloud
- Go to https://share.streamlit.io/
- Click "New app"
- Connect your GitHub repo
- Set main file: `web_agent.py`
- Deploy!

---

## ⚠️ Important Notes

### PMS/AIF Issue
Your logs show PMS/AIF are NOT being updated from factsheets:
```
🔍 PMS/AIF FETCH RESULT: None
⚠️ PMS: Using transaction price (SEBI data not available)
```

**This means the background update is not working!**

The factsheet update should happen in `pms_aif_updater.py` but it's not being called properly during file upload.

### Fix Required
Check line 1141 in `web_agent.py`:
```python
pms_count = update_pms_aif_for_file(user_id, file_id)
```

This should be updating PMS/AIF from factsheets, but logs show it's not working.

---

## 📊 Current Deployment Size

**Before cleanup:** ~1000+ files, ~500MB  
**After cleanup:** ~12 files, ~5MB  

This will:
- ✅ Fix the inotify limit error
- ✅ Speed up deployment
- ✅ Make the repo cleaner
- ✅ Reduce costs

---

**Created:** October 11, 2025  
**Status:** Ready to clean and deploy

