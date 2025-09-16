-- Create table for storing AI analysis reports
CREATE TABLE IF NOT EXISTS ai_analysis_reports (
    id SERIAL PRIMARY KEY,
    report_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    report_type VARCHAR(50) DEFAULT 'general_analysis'
);

-- Create indexes for better query performance
CREATE INDEX idx_ai_reports_created_at ON ai_analysis_reports (created_at DESC);
CREATE INDEX idx_ai_reports_type ON ai_analysis_reports (report_type);

-- Add GIN index for JSONB queries
CREATE INDEX idx_ai_reports_data_gin ON ai_analysis_reports USING gin (report_data);

-- Create a view for latest reports
CREATE OR REPLACE VIEW latest_ai_reports AS
SELECT 
    id,
    report_data->>'timestamp' as report_timestamp,
    report_data->'summary'->>'platformHealth' as platform_health,
    report_data->'summary'->>'totalUsers' as total_users,
    report_data->'summary'->>'totalCourses' as total_courses,
    report_data->'summary'->>'overallEngagement' as overall_engagement,
    created_at
FROM ai_analysis_reports
ORDER BY created_at DESC;

-- Function to get report insights
CREATE OR REPLACE FUNCTION get_report_insights(report_id INTEGER)
RETURNS TABLE(insight TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT jsonb_array_elements_text(report_data->'recommendations') as insight
    FROM ai_analysis_reports
    WHERE id = report_id;
END;
$$ LANGUAGE plpgsql;

-- Sample query to get latest platform metrics
COMMENT ON TABLE ai_analysis_reports IS 'Stores AI-generated analysis reports from n8n workflows';

-- Grant permissions (adjust as needed)
-- GRANT SELECT, INSERT ON ai_analysis_reports TO n8n_user;
-- GRANT USAGE, SELECT ON SEQUENCE ai_analysis_reports_id_seq TO n8n_user;