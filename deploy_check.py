#!/usr/bin/env python3
"""
Deploy Readiness Checker for Events Dashboard
Verifica se todos os arquivos necessários para deployment estão presentes e configurados corretamente.
"""

import os
import json
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Verifica se um arquivo existe"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} - MISSING")
        return False

def check_backend_files():
    """Verifica arquivos necessários para o backend"""
    print("🔍 Checking Backend Files...")
    
    files_to_check = [
        ("backend.py", "FastAPI application"),
        ("requirements.txt", "Python dependencies"),
        ("Procfile", "Process configuration for deployment"),
        ("runtime.txt", "Python version specification"),
        ("render.yaml", "Render deployment configuration"),
        ("database_utils.py", "Database utilities")
    ]
    
    all_present = True
    for filepath, description in files_to_check:
        if not check_file_exists(filepath, description):
            all_present = False
    
    return all_present

def check_frontend_files():
    """Verifica arquivos necessários para o frontend"""
    print("\n🔍 Checking Frontend Files...")
    
    frontend_files = [
        ("frontend/package.json", "Package configuration"),
        ("frontend/src/components/EventsPage.jsx", "Main React component"),
        ("frontend/src/App.js", "React App component"),
        ("frontend/src/index.js", "React entry point"),
        ("frontend/public/index.html", "HTML template"),
        ("frontend/tailwind.config.js", "Tailwind CSS configuration"),
        ("frontend/postcss.config.js", "PostCSS configuration"),
        ("frontend/env.example", "Environment variables example")
    ]
    
    all_present = True
    for filepath, description in frontend_files:
        if not check_file_exists(filepath, description):
            all_present = False
    
    return all_present

def check_package_json():
    """Verifica se o package.json tem os scripts necessários"""
    print("\n🔍 Checking package.json configuration...")
    
    try:
        with open("frontend/package.json", "r") as f:
            package_data = json.load(f)
        
        required_scripts = ["start", "build"]
        scripts = package_data.get("scripts", {})
        
        for script in required_scripts:
            if script in scripts:
                print(f"✅ Script '{script}': {scripts[script]}")
            else:
                print(f"❌ Script '{script}': MISSING")
                return False
        
        # Check dependencies
        dependencies = package_data.get("dependencies", {})
        required_deps = ["react", "react-dom"]
        
        for dep in required_deps:
            if dep in dependencies:
                print(f"✅ Dependency '{dep}': {dependencies[dep]}")
            else:
                print(f"❌ Dependency '{dep}': MISSING")
                return False
        
        return True
        
    except FileNotFoundError:
        print("❌ frontend/package.json not found")
        return False
    except json.JSONDecodeError:
        print("❌ frontend/package.json is not valid JSON")
        return False

def check_requirements():
    """Verifica se requirements.txt tem as dependências necessárias"""
    print("\n🔍 Checking requirements.txt...")
    
    try:
        with open("requirements.txt", "r") as f:
            requirements = f.read()
        
        required_packages = [
            "fastapi",
            "uvicorn", 
            "gunicorn",
            "sqlalchemy",
            "psycopg2-binary"
        ]
        
        all_present = True
        for package in required_packages:
            if package in requirements.lower():
                print(f"✅ Package '{package}': Found")
            else:
                print(f"❌ Package '{package}': MISSING")
                all_present = False
        
        return all_present
        
    except FileNotFoundError:
        print("❌ requirements.txt not found")
        return False

def check_environment_variables():
    """Verifica configuração de variáveis de ambiente"""
    print("\n🔍 Checking Environment Variables Configuration...")
    
    # Check backend CORS configuration
    try:
        with open("backend.py", "r") as f:
            backend_content = f.read()
        
        if "FRONTEND_URL" in backend_content:
            print("✅ Backend configured for environment variable FRONTEND_URL")
        else:
            print("❌ Backend missing FRONTEND_URL environment variable support")
            return False
        
        if "vercel.app" in backend_content or "netlify.app" in backend_content:
            print("✅ Backend CORS configured for deployment platforms")
        else:
            print("❌ Backend CORS missing deployment platform support")
            return False
            
    except FileNotFoundError:
        print("❌ backend.py not found")
        return False
    
    # Check frontend API URL configuration  
    try:
        with open("frontend/src/components/EventsPage.jsx", "r") as f:
            frontend_content = f.read()
        
        if "REACT_APP_API_URL" in frontend_content:
            print("✅ Frontend configured for environment variable REACT_APP_API_URL")
        else:
            print("❌ Frontend missing REACT_APP_API_URL environment variable support")
            return False
            
    except FileNotFoundError:
        print("❌ frontend/src/components/EventsPage.jsx not found")
        return False
    
    return True

def generate_deployment_checklist():
    """Gera checklist de deployment"""
    print("\n📋 DEPLOYMENT CHECKLIST")
    print("=" * 50)
    
    checklist = [
        "1. ✅ Commit and push all changes to GitHub",
        "2. ✅ Create account on Render.com",
        "3. ✅ Create account on Vercel.com", 
        "4. ✅ Deploy backend to Render:",
        "   - Connect GitHub repository",
        "   - Set build command: pip install -r requirements.txt",
        "   - Set start command: gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend:app --bind 0.0.0.0:$PORT",
        "   - Add environment variable: DATABASE_URL",
        "5. ✅ Deploy frontend to Vercel:",
        "   - Connect GitHub repository", 
        "   - Set root directory: frontend",
        "   - Add environment variable: REACT_APP_API_URL (backend URL)",
        "6. ✅ Update backend FRONTEND_URL with Vercel URL",
        "7. ✅ Test both applications"
    ]
    
    for item in checklist:
        print(item)

def main():
    """Função principal"""
    print("🚀 EVENTS DASHBOARD - DEPLOYMENT READINESS CHECK")
    print("=" * 60)
    
    checks_passed = []
    
    # Run all checks
    checks_passed.append(check_backend_files())
    checks_passed.append(check_frontend_files())
    checks_passed.append(check_package_json())
    checks_passed.append(check_requirements())
    checks_passed.append(check_environment_variables())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    
    if all(checks_passed):
        print("🎉 ALL CHECKS PASSED! Your application is ready for deployment!")
        generate_deployment_checklist()
        print("\n💡 Next steps:")
        print("   1. Read DEPLOYMENT_GUIDE.md for detailed instructions")
        print("   2. Push your code to GitHub if you haven't already")
        print("   3. Follow the deployment guide for Render + Vercel")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above before deploying.")
        print("\n🔧 Common fixes:")
        print("   - Make sure all files are present")
        print("   - Check file contents for required configurations")
        print("   - Run the application locally first to ensure it works")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 