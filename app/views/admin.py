import logging
from flask import Blueprint, jsonify, render_template_string
import db_manager

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

# Simple HTML admin template
ADMIN_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Podcast Pro - Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 20px auto; padding: 20px; }
        .header { border-bottom: 2px solid #007bff; padding-bottom: 20px; margin-bottom: 30px; }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
        .stat-label { color: #6c757d; }
        .jobs-section { margin-top: 30px; }
        .job-card { background: white; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 15px; }
        .job-header { display: flex; justify-content: between; align-items: center; margin-bottom: 10px; }
        .job-title { font-weight: bold; font-size: 1.2em; }
        .job-status { padding: 4px 12px; border-radius: 20px; font-size: 0.9em; }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-processing { background: #cce5ff; color: #004085; }
        .status-completed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        .job-meta { color: #6c757d; font-size: 0.9em; }
        .refresh-btn { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .refresh-btn:hover { background: #218838; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Podcast Pro - Admin Dashboard</h1>
        <button class="refresh-btn" onclick="location.reload()">Refresh</button>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{{ stats.total }}</div>
            <div class="stat-label">Total Jobs</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.pending }}</div>
            <div class="stat-label">Pending</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.processing }}</div>
            <div class="stat-label">Processing</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.completed }}</div>
            <div class="stat-label">Completed</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{{ stats.failed }}</div>
            <div class="stat-label">Failed</div>
        </div>
    </div>
    
    <div class="jobs-section">
        <h2>Recent Jobs</h2>
        {% if jobs %}
            {% for job in jobs %}
            <div class="job-card">
                <div class="job-header">
                    <div class="job-title">{{ job.title }}</div>
                    <div class="job-status status-{{ job.status }}">{{ job.status.upper() }}</div>
                </div>
                <div class="job-meta">
                    <strong>ID:</strong> {{ job.id }} | 
                    <strong>Type:</strong> {{ job.job_type }} | 
                    <strong>Created:</strong> {{ job.created_at }} |
                    <strong>Priority:</strong> {{ job.priority }}
                </div>
                {% if job.description %}
                <div style="margin-top: 10px; color: #495057;">{{ job.description }}</div>
                {% endif %}
                {% if job.file_path %}
                <div style="margin-top: 10px; color: #6c757d; font-size: 0.9em;">
                    <strong>File:</strong> {{ job.file_path }}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="job-card">
                <div style="text-align: center; color: #6c757d;">No jobs found</div>
            </div>
        {% endif %}
    </div>
    
    <p><a href="/">← Back to Submit Job</a></p>
</body>
</html>
"""

@admin_bp.route('/admin')
def admin_dashboard():
    """Admin dashboard showing job statistics and recent jobs"""
    try:
        # Get all jobs for statistics
        all_jobs = db_manager.get_all_jobs()
        
        # Calculate statistics
        stats = {
            'total': len(all_jobs),
            'pending': len([j for j in all_jobs if j.get('status') == 'pending']),
            'processing': len([j for j in all_jobs if j.get('status') == 'processing']),
            'completed': len([j for j in all_jobs if j.get('status') == 'completed']),
            'failed': len([j for j in all_jobs if j.get('status') == 'failed'])
        }
        
        # Get recent jobs (last 20)
        recent_jobs = all_jobs[:20] if all_jobs else []
        
        return render_template_string(ADMIN_DASHBOARD, stats=stats, jobs=recent_jobs)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {e}")
        return f"Error loading admin dashboard: {str(e)}", 500

@admin_bp.route('/api/jobs')
def api_jobs():
    """API endpoint to get all jobs as JSON"""
    try:
        jobs = db_manager.get_all_jobs()
        return jsonify(jobs)
        
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        return jsonify({'error': 'Failed to get jobs'}), 500

@admin_bp.route('/api/stats')
def api_stats():
    """API endpoint to get job statistics"""
    try:
        all_jobs = db_manager.get_all_jobs()
        
        stats = {
            'total': len(all_jobs),
            'pending': len([j for j in all_jobs if j.get('status') == 'pending']),
            'processing': len([j for j in all_jobs if j.get('status') == 'processing']),
            'completed': len([j for j in all_jobs if j.get('status') == 'completed']),
            'failed': len([j for j in all_jobs if j.get('status') == 'failed'])
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500