# 🚀 Deployment Guide

## Streamlit Cloud Deployment

### Step 1: Prepare Repository

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/wealth-manager.git
git push -u origin main
```

2. **Verify Files**
Ensure these files are in your repository:
- `web_agent.py` (main app)
- `requirements.txt`
- `database_shared.py`
- All Python modules
- `RUN_THIS_FIRST.sql`
- `ADD_PDF_STORAGE.sql`
- `README.md`

### Step 2: Set Up Supabase

1. **Create Supabase Project**
   - Go to [supabase.com](https://supabase.com)
   - Create a new project
   - Note your project URL and anon key

2. **Run SQL Scripts**
   - Open SQL Editor in Supabase
   - Run `RUN_THIS_FIRST.sql` (creates main tables)
   - Run `ADD_PDF_STORAGE.sql` (creates PDF storage)

3. **Verify Tables**
   Check that these tables exist:
   - `users`
   - `stock_master`
   - `user_transactions`
   - `historical_prices`
   - `user_pdfs`

### Step 3: Deploy to Streamlit Cloud

1. **Go to Streamlit Cloud**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub

2. **Create New App**
   - Click "New app"
   - Select your repository
   - Main file: `web_agent.py`
   - Click "Deploy"

3. **Add Secrets**
   - Go to app settings → Secrets
   - Add your configuration:

```toml
[supabase]
url = "https://your-project.supabase.co"
key = "your-supabase-anon-key"

[api_keys]
open_ai = "sk-your-openai-api-key"
gemini = "your-gemini-api-key"
```

4. **Save and Reboot**
   - Save secrets
   - Reboot app
   - Wait for deployment to complete

### Step 4: Verify Deployment

1. **Test Registration**
   - Open your app URL
   - Register a new account
   - Verify user is created

2. **Test File Upload**
   - Upload a CSV file
   - Check transactions are imported
   - Verify prices are fetched

3. **Test AI Features**
   - Open AI Assistant
   - Upload a PDF
   - Ask a question
   - Verify responses

## Environment Variables

### Required Secrets

| Key | Description | Example |
|-----|-------------|---------|
| `supabase.url` | Supabase project URL | `https://abc123.supabase.co` |
| `supabase.key` | Supabase anon key | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `api_keys.open_ai` | OpenAI API key | `sk-proj-...` |
| `api_keys.gemini` | Gemini API key (optional) | `AIzaSy...` |

### Getting API Keys

**Supabase:**
1. Go to Project Settings → API
2. Copy "Project URL"
3. Copy "anon public" key

**OpenAI:**
1. Go to [platform.openai.com](https://platform.openai.com)
2. Navigate to API Keys
3. Create new secret key

**Gemini (Optional):**
1. Go to [makersuite.google.com](https://makersuite.google.com)
2. Get API key

## Local Development

### Setup

1. **Clone Repository**
```bash
git clone https://github.com/yourusername/wealth-manager.git
cd wealth-manager
```

2. **Create Virtual Environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Secrets**
```bash
mkdir .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your actual keys
```

5. **Run Application**
```bash
streamlit run web_agent.py
```

## Troubleshooting

### Common Deployment Issues

**1. ModuleNotFoundError**
- Check `requirements.txt` includes all dependencies
- Redeploy after updating requirements

**2. Database Connection Failed**
- Verify Supabase URL and key in secrets
- Check Supabase project is active
- Verify RLS policies are enabled

**3. API Key Errors**
- Check secrets are properly formatted (TOML syntax)
- Verify API keys are valid and active
- Check key names match code (e.g., `open_ai` not `openai`)

**4. App Crashes on Startup**
- Check logs in Streamlit Cloud
- Verify all SQL scripts were run
- Check for syntax errors in secrets

**5. Slow Performance**
- Enable caching (already enabled by default)
- Check database indexes (created by SQL scripts)
- Consider upgrading Streamlit Cloud plan

### Debugging

**View Logs:**
- Streamlit Cloud: App menu → Logs
- Local: Terminal output

**Check Database:**
- Supabase: Table Editor
- Run diagnostic queries:
```sql
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM user_transactions;
SELECT COUNT(*) FROM historical_prices;
```

**Test API Keys:**
```python
import openai
openai.api_key = "your-key"
# Try a simple API call
```

## Performance Optimization

### Streamlit Cloud

1. **Use Caching**
   - Already implemented in code
   - 5-10 minute TTL for expensive operations

2. **Optimize Database Queries**
   - Indexes already created
   - Use silent operations for charts

3. **Lazy Loading**
   - Heavy features load on demand
   - Conditional rendering implemented

### Database Optimization

1. **Indexes**
   - All indexes created in SQL scripts
   - Optimized for common queries

2. **Connection Pooling**
   - Handled by Supabase client
   - Automatic connection management

## Monitoring

### Key Metrics

1. **App Performance**
   - Page load time
   - Query execution time
   - Cache hit rate

2. **Database**
   - Query count
   - Response time
   - Storage usage

3. **API Usage**
   - OpenAI API calls
   - Rate limits
   - Cost tracking

### Streamlit Cloud Metrics

- View in app dashboard
- Monitor resource usage
- Check error logs

## Scaling

### Handling Growth

1. **Database**
   - Supabase auto-scales
   - Monitor storage limits
   - Optimize queries as needed

2. **API Limits**
   - OpenAI: Monitor usage
   - Implement rate limiting if needed
   - Cache AI responses

3. **Streamlit Cloud**
   - Free tier: 1 GB RAM
   - Upgrade if needed
   - Consider self-hosting for large scale

## Security Best Practices

1. **Secrets Management**
   - Never commit secrets to Git
   - Use `.gitignore` for `secrets.toml`
   - Rotate keys periodically

2. **Database Security**
   - RLS enabled by default
   - User data isolated
   - Secure password hashing

3. **API Security**
   - Keep API keys private
   - Monitor usage for anomalies
   - Set spending limits

## Backup & Recovery

### Database Backup

**Supabase:**
- Automatic daily backups
- Point-in-time recovery available
- Manual backups: Project Settings → Database → Backups

### Code Backup

**GitHub:**
- Regular commits
- Tag releases
- Use branches for features

## Support

### Getting Help

1. **Documentation**
   - Check README.md
   - Review SQL scripts
   - Read code comments

2. **Streamlit Community**
   - [Streamlit Forum](https://discuss.streamlit.io)
   - [Streamlit Docs](https://docs.streamlit.io)

3. **Supabase Support**
   - [Supabase Docs](https://supabase.com/docs)
   - [Supabase Discord](https://discord.supabase.com)

## Checklist

### Pre-Deployment

- [ ] All code committed to GitHub
- [ ] `requirements.txt` updated
- [ ] Supabase project created
- [ ] SQL scripts executed
- [ ] Tables verified
- [ ] API keys obtained
- [ ] `.gitignore` configured

### Deployment

- [ ] App deployed to Streamlit Cloud
- [ ] Secrets configured
- [ ] App starts without errors
- [ ] Registration works
- [ ] File upload works
- [ ] Charts display correctly
- [ ] AI Assistant responds

### Post-Deployment

- [ ] Test all features
- [ ] Monitor logs for errors
- [ ] Check database connections
- [ ] Verify API usage
- [ ] Share app URL
- [ ] Document any issues

---

**Your app is now live! 🎉**

Access it at: `https://your-app.streamlit.app`

