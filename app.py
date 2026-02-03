import os
from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import re

load_dotenv()
app = Flask(__name__)

# -------------------- PDF EXTRACT --------------------
def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    return "".join(page.extract_text() for page in reader.pages)

# -------------------- EXTRACT SKILLS --------------------
def extract_skills(text):
    skills = [
        "Python", "JavaScript", "Java", "C++", "C#", "Ruby", "PHP", "Swift",
        "React", "Angular", "Vue", "Django", "Flask", "Node.js", "Express",
        "SQL", "MySQL", "MongoDB", "PostgreSQL", "Docker", "Kubernetes",
        "AWS", "Azure", "GCP", "Git", "Linux", "HTML", "CSS",
        "REST API", "GraphQL", "Machine Learning", "AI", "Data Analysis",
        "Agile", "Scrum", "Project Management", "Leadership", "Communication",
        "Problem Solving", "Teamwork", "Critical Thinking", "Time Management"
    ]
    return list(set([s for s in skills if s.lower() in text.lower()]))

# -------------------- ATS SCORE --------------------
def calculate_ats_score(text):
    score = 50
    checks = [
        ("email", 5), ("phone", 5), ("experience", 10),
        ("education", 10), ("skills", 10), ("project", 5)
    ]
    for keyword, points in checks:
        if keyword in text.lower():
            score += points
    if len(text) > 500:
        score += 5
    return min(score, 100)

# -------------------- JOB MATCH --------------------
def calculate_job_match(resume_text, job_desc):
    resume_skills = set(extract_skills(resume_text))
    job_skills = set(extract_skills(job_desc))
    if not job_skills:
        return 50
    matched = len(resume_skills & job_skills)
    return min(int((matched / len(job_skills)) * 100), 100)

# -------------------- MISSING SKILLS --------------------
def get_missing_skills(resume_text, job_desc):
    return list(set(extract_skills(job_desc)) - set(extract_skills(resume_text)))

# -------------------- SUGGESTIONS --------------------
def get_suggestions(resume_text, job_desc):
    suggestions = []
    rl = resume_text.lower()
    
    if len(resume_text) < 300:
        suggestions.append("Resume is too short. Add more details about your experience and achievements.")
    
    if "achievement" not in rl and "accomplished" not in rl:
        suggestions.append("Include quantifiable achievements with specific metrics (e.g., 'Increased sales by 30%').")
    
    if "responsibility" not in rl and "responsible" not in rl:
        suggestions.append("Highlight your key responsibilities and contributions in each role.")
    
    if resume_text.count("\n") < 5:
        suggestions.append("Use better formatting with clear sections and bullet points for readability.")
    
    missing = get_missing_skills(resume_text, job_desc)
    if missing:
        suggestions.append(f"Consider adding these skills from the job description: {', '.join(missing[:3])}")
    
    if not any(verb in rl for verb in ['developed', 'implemented', 'led', 'managed']):
        suggestions.append("Start bullet points with strong action verbs: Developed, Implemented, Led, Managed, Achieved.")
    
    suggestions.append("Include relevant certifications, awards, and professional development.")
    
    return suggestions[:6]

# -------------------- PDF REPORT --------------------
def generate_pdf_report(data):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title = ParagraphStyle('T', parent=styles['Heading1'], fontSize=24, 
                          textColor=colors.HexColor('#D6B9FC'), alignment=1, spaceAfter=12)
    heading = ParagraphStyle('H', parent=styles['Heading2'], fontSize=14,
                            textColor=colors.HexColor('#838CE5'), spaceAfter=8, spaceBefore=12)
    body = ParagraphStyle('B', parent=styles['Normal'], fontSize=11, spaceAfter=6)
    
    elements = []
    
    # Title
    elements.append(Paragraph("Resume Analysis Report", title))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Scores
    elements.append(Paragraph("Analysis Scores", heading))
    score_data = [['Metric', 'Score'], ['ATS Score', f"{data.get('ats_score', 0)}%"]]
    if data.get('job_match'):
        score_data.append(['Job Match', f"{data.get('job_match', 0)}%"])
    
    table = Table(score_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#838CE5')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Skills
    elements.append(Paragraph("Detected Skills", heading))
    if data.get('skills'):
        elements.append(Paragraph(", ".join(data.get('skills', [])), body))
    else:
        elements.append(Paragraph("No skills detected", body))
    elements.append(Spacer(1, 0.2*inch))
    
    # Missing Skills
    if data.get('missing_skills'):
        elements.append(Paragraph("Missing Skills (From Job Description)", heading))
        elements.append(Paragraph(", ".join(data['missing_skills']), body))
        elements.append(Spacer(1, 0.2*inch))
    
    # Suggestions
    elements.append(Paragraph("Improvement Suggestions", heading))
    for i, s in enumerate(data.get('feedback', []), 1):
        elements.append(Paragraph(f"{i}. {s}", body))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# -------------------- ROUTES --------------------
@app.route("/", methods=["GET", "POST"])
def index():
    data = {}
    
    if request.method == "POST":
        resume_file = request.files.get("resume")
        job_desc = request.form.get("job_desc")

        if resume_file:
            try:
                text = extract_text_from_pdf(resume_file)
                
                # Basic analysis
                data["resume_text"] = text
                data["ats_score"] = calculate_ats_score(text)
                data["skills"] = extract_skills(text)
                data["feedback"] = get_suggestions(text, job_desc or "")
                
                # Job matching if description provided
                if job_desc and job_desc.strip():
                    data["job_match"] = calculate_job_match(text, job_desc)
                    data["missing_skills"] = get_missing_skills(text, job_desc)
                
            except Exception as e:
                print(f"Error processing resume: {e}")
                data["error"] = "Error processing your resume. Please ensure it's a valid PDF file."

    return render_template("index.html", data=data)

@app.route("/download-report", methods=["POST"])
def download_report():
    data = {
        'ats_score': request.form.get('ats_score', 0),
        'job_match': request.form.get('job_match'),
        'skills': request.form.getlist('skills'),
        'missing_skills': request.form.getlist('missing_skills'),
        'feedback': request.form.getlist('feedback')
    }
    
    buffer = generate_pdf_report(data)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'resume_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    )

if __name__ == "__main__":
    app.run(debug=True)