// LMS-n8n Integration Helper
class N8nAIAnalytics {
  constructor(n8nWebhookUrl, apiKey = null) {
    this.webhookUrl = n8nWebhookUrl;
    this.apiKey = apiKey;
  }

  // Trigger AI analysis
  async triggerAnalysis(customParams = {}) {
    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      if (this.apiKey) {
        headers['Authorization'] = `Bearer ${this.apiKey}`;
      }

      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          timestamp: new Date().toISOString(),
          source: 'lms-application',
          ...customParams
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error triggering n8n analysis:', error);
      throw error;
    }
  }

  // Get latest analysis report from database
  async getLatestReport() {
    // This would typically connect to your database
    // Example implementation for your LMS
    const query = `
      SELECT 
        id,
        report_data,
        created_at
      FROM ai_analysis_reports 
      ORDER BY created_at DESC 
      LIMIT 1
    `;
    
    // Replace with your database connection logic
    // return await db.query(query);
    
    console.log('Query to run:', query);
    return null;
  }

  // Get report insights for display in LMS dashboard
  async getReportSummary(reportId = null) {
    const query = reportId 
      ? `
        SELECT 
          report_data->'summary' as summary,
          report_data->'recommendations' as recommendations,
          created_at
        FROM ai_analysis_reports 
        WHERE id = $1
      `
      : `
        SELECT 
          report_data->'summary' as summary,
          report_data->'recommendations' as recommendations,
          created_at
        FROM ai_analysis_reports 
        ORDER BY created_at DESC 
        LIMIT 1
      `;
    
    console.log('Summary query:', query);
    return null;
  }

  // Schedule periodic analysis
  scheduleAnalysis(intervalHours = 24) {
    const interval = intervalHours * 60 * 60 * 1000; // Convert to milliseconds
    
    return setInterval(async () => {
      try {
        console.log('Running scheduled AI analysis...');
        await this.triggerAnalysis({
          source: 'scheduled',
          interval: intervalHours
        });
        console.log('Scheduled analysis completed');
      } catch (error) {
        console.error('Scheduled analysis failed:', error);
      }
    }, interval);
  }
}

// Usage examples:

// Initialize the integration
const analytics = new N8nAIAnalytics('http://your-ec2-ip:5678/webhook/ai-analysis-webhook');

// Trigger analysis on demand
async function runAnalysis() {
  try {
    const result = await analytics.triggerAnalysis({
      userId: 'admin',
      reason: 'manual-trigger'
    });
    console.log('Analysis result:', result);
  } catch (error) {
    console.error('Analysis failed:', error);
  }
}

// Schedule daily analysis
// const scheduleId = analytics.scheduleAnalysis(24);

// For Node.js/Express integration:
if (typeof module !== 'undefined' && module.exports) {
  module.exports = N8nAIAnalytics;
}

// For frontend/React integration:
if (typeof window !== 'undefined') {
  window.N8nAIAnalytics = N8nAIAnalytics;
}

/* 
Example usage in your LMS routes:

// Express.js route example
app.post('/api/trigger-analysis', async (req, res) => {
  try {
    const analytics = new N8nAIAnalytics(process.env.N8N_WEBHOOK_URL);
    const result = await analytics.triggerAnalysis({
      userId: req.user.id,
      source: 'api-endpoint'
    });
    res.json({ success: true, data: result });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// Dashboard route to show analytics
app.get('/api/analytics-summary', async (req, res) => {
  try {
    // Query your database for the latest report
    const latestReport = await db.query(`
      SELECT report_data 
      FROM ai_analysis_reports 
      ORDER BY created_at DESC 
      LIMIT 1
    `);
    
    if (latestReport.rows.length > 0) {
      res.json({
        success: true,
        data: latestReport.rows[0].report_data
      });
    } else {
      res.json({
        success: false,
        message: 'No analytics reports found'
      });
    }
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});
*/