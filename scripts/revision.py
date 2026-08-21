#!/usr/bin/env python3
"""
ArciTEK.AI Automated Revision System

This script manages daily revisions, tracking updates, fixes, and improvements
toward the 100th revision deployment milestone.

Usage:
    python3 scripts/revision.py              # Create new revision
    python3 scripts/revision.py --status     # Show current status
    python3 scripts/revision.py --plan       # Show revision plan
    python3 scripts/revision.py --report     # Generate report

"Every build is a work of art" - infinite♾2025
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Configuration
REPO_ROOT = Path(__file__).parent.parent
REVISIONS_FILE = REPO_ROOT / "REVISIONS.md"
REVISION_DATA_FILE = REPO_ROOT / "config" / "revision_data.json"
ROADMAP_FILE = REPO_ROOT / "docs" / "ROADMAP.md"


class RevisionManager:
    """Manages the daily revision system"""
    
    def __init__(self):
        self.repo_root = REPO_ROOT
        self.revision_data = self._load_revision_data()
        self.current_revision = self.revision_data.get("current_revision", 0)
        
    def _load_revision_data(self) -> Dict:
        """Load revision tracking data"""
        if REVISION_DATA_FILE.exists():
            with open(REVISION_DATA_FILE, 'r') as f:
                return json.load(f)
        return {
            "current_revision": 0,
            "start_date": datetime.now().isoformat(),
            "revisions": [],
            "metrics": {
                "total_features": 0,
                "total_bugfixes": 0,
                "total_performance_improvements": 0,
                "test_coverage": 0.0,
                "security_score": 100
            }
        }
    
    def _save_revision_data(self):
        """Save revision tracking data"""
        REVISION_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REVISION_DATA_FILE, 'w') as f:
            json.dump(self.revision_data, f, indent=2)
    
    def _run_command(self, cmd: List[str]) -> tuple:
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.repo_root
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def _get_version_for_revision(self, revision: int) -> str:
        """Get version number for revision"""
        if revision <= 10:
            return f"1.0.{revision}"
        elif revision <= 20:
            return f"1.1.{revision - 10}"
        elif revision <= 30:
            return f"1.2.{revision - 20}"
        elif revision <= 40:
            return f"1.3.{revision - 30}"
        elif revision <= 50:
            return f"1.4.{revision - 40}"
        elif revision <= 60:
            return f"1.5.{revision - 50}"
        elif revision <= 70:
            return f"1.6.{revision - 60}"
        elif revision <= 80:
            return f"1.7.{revision - 70}"
        elif revision <= 90:
            return f"1.8.{revision - 80}"
        elif revision < 100:
            return f"1.9.{revision - 90}"
        else:
            return "2.0.0"
    
    def _get_focus_for_revision(self, revision: int) -> str:
        """Get focus area for revision"""
        if revision <= 10:
            return "Foundation & Stability"
        elif revision <= 20:
            return "Quantum Enhancements"
        elif revision <= 30:
            return "AI Model Expansion"
        elif revision <= 40:
            return "Performance Optimization"
        elif revision <= 50:
            return "Developer Tools"
        elif revision <= 60:
            return "UI/UX Improvements"
        elif revision <= 70:
            return "Integration Expansion"
        elif revision <= 80:
            return "Security & Compliance"
        elif revision <= 90:
            return "Advanced Features"
        elif revision < 100:
            return "Pre-2.0 Polish"
        else:
            return "Major Release v2.0.0"
    
    def run_quality_checks(self) -> Dict:
        """Run code quality checks"""
        print("🔍 Running quality checks...")
        
        checks = {
            "linting": False,
            "formatting": False,
            "type_checking": False,
            "tests": False,
            "security": False
        }
        
        # Run black (formatting check)
        success, _, _ = self._run_command(
            ["black", "--check", "arcitek_core/", "quantum/", "ai_models/", "scripts/"]
        )
        checks["formatting"] = success
        
        # Run flake8 (linting)
        success, _, _ = self._run_command(
            ["flake8", "arcitek_core/", "--count", "--max-line-length=100"]
        )
        checks["linting"] = success
        
        # Run mypy (type checking)
        success, _, _ = self._run_command(
            ["mypy", "arcitek_core/", "--ignore-missing-imports"]
        )
        checks["type_checking"] = success
        
        # Run tests
        success, _, _ = self._run_command(
            ["python3", "-m", "pytest", "tests/", "-v"]
        )
        checks["tests"] = success
        
        # Run security check
        success, _, _ = self._run_command(
            ["bandit", "-r", "arcitek_core/", "-f", "json", "-o", "bandit-report.json"]
        )
        checks["security"] = success
        
        return checks
    
    def get_test_coverage(self) -> float:
        """Get current test coverage percentage"""
        success, output, _ = self._run_command(
            ["python3", "-m", "pytest", "--cov=arcitek_core", "--cov-report=json", "tests/"]
        )
        
        if success:
            try:
                with open(self.repo_root / "coverage.json", 'r') as f:
                    coverage_data = json.load(f)
                    return coverage_data.get("totals", {}).get("percent_covered", 0.0)
            except:
                pass
        
        return 0.0
    
    def create_revision(self, category: str, description: str, changes: List[str]) -> bool:
        """Create a new revision"""
        next_revision = self.current_revision + 1
        version = self._get_version_for_revision(next_revision)
        focus = self._get_focus_for_revision(next_revision)
        
        print(f"\n🚀 Creating Revision r{next_revision}")
        print(f"📦 Version: {version}")
        print(f"🎯 Focus: {focus}")
        print(f"📂 Category: {category}")
        
        # Run quality checks
        checks = self.run_quality_checks()
        
        if not all(checks.values()):
            print("\n❌ Quality checks failed:")
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"  {status} {check}")
            
            response = input("\nContinue anyway? (y/N): ")
            if response.lower() != 'y':
                return False
        
        # Get metrics
        test_coverage = self.get_test_coverage()
        
        # Update revision data
        revision_entry = {
            "revision": next_revision,
            "version": version,
            "date": datetime.now().isoformat(),
            "category": category,
            "description": description,
            "changes": changes,
            "focus": focus,
            "metrics": {
                "test_coverage": test_coverage,
                "checks_passed": all(checks.values())
            }
        }
        
        self.revision_data["current_revision"] = next_revision
        self.revision_data["revisions"].append(revision_entry)
        
        # Update category counters
        if category == "feature":
            self.revision_data["metrics"]["total_features"] += 1
        elif category == "bugfix":
            self.revision_data["metrics"]["total_bugfixes"] += 1
        elif category == "performance":
            self.revision_data["metrics"]["total_performance_improvements"] += 1
        
        self.revision_data["metrics"]["test_coverage"] = test_coverage
        
        # Save data
        self._save_revision_data()
        
        # Update REVISIONS.md
        self._update_revisions_file(revision_entry)
        
        # Update VERSION file
        with open(self.repo_root / "VERSION", 'w') as f:
            f.write(version)
        
        # Create git commit
        commit_message = self._generate_commit_message(revision_entry)
        self._create_git_commit(commit_message)
        
        print(f"\n✅ Revision r{next_revision} created successfully!")
        print(f"📊 Test Coverage: {test_coverage:.1f}%")
        print(f"🎯 Progress to r100: {next_revision}/100 ({next_revision}%)")
        
        # Check for milestone
        if next_revision % 10 == 0:
            print(f"\n🎉 MILESTONE REACHED: r{next_revision}!")
            print("Consider creating a release and posting an update to the community.")
        
        return True
    
    def _update_revisions_file(self, revision_entry: Dict):
        """Update REVISIONS.md file"""
        if not REVISIONS_FILE.exists():
            with open(REVISIONS_FILE, 'w') as f:
                f.write("# ArciTEK.AI Revisions\n\n")
                f.write("> **\"Every build is a work of art\"** - infinite♾2025\n\n")
                f.write("This file tracks all daily revisions toward the r100 deployment milestone.\n\n")
                f.write("---\n\n")
        
        entry = f"""## Revision r{revision_entry['revision']} - {datetime.fromisoformat(revision_entry['date']).strftime('%Y-%m-%d')}

**Version:** {revision_entry['version']}  
**Category:** {revision_entry['category']}  
**Focus:** {revision_entry['focus']}  
**Description:** {revision_entry['description']}

### Changes
"""
        for change in revision_entry['changes']:
            entry += f"- {change}\n"
        
        entry += f"""
### Metrics
- Test Coverage: {revision_entry['metrics']['test_coverage']:.1f}%
- Quality Checks: {'✅ Passed' if revision_entry['metrics']['checks_passed'] else '⚠️ Issues'}

---

"""
        
        # Prepend to file (newest first)
        with open(REVISIONS_FILE, 'r') as f:
            content = f.read()
        
        # Find where to insert (after the header)
        header_end = content.find("---\n\n") + 5
        new_content = content[:header_end] + entry + content[header_end:]
        
        with open(REVISIONS_FILE, 'w') as f:
            f.write(new_content)
    
    def _generate_commit_message(self, revision_entry: Dict) -> str:
        """Generate git commit message"""
        category_prefix = {
            "feature": "feat",
            "bugfix": "fix",
            "performance": "perf",
            "security": "security",
            "documentation": "docs",
            "testing": "test",
            "ui": "ui",
            "refactor": "refactor",
            "deployment": "deploy",
            "automation": "chore"
        }
        
        prefix = category_prefix.get(revision_entry['category'], 'chore')
        
        message = f"{prefix}: r{revision_entry['revision']} - {revision_entry['description']}\n\n"
        
        for change in revision_entry['changes']:
            message += f"- {change}\n"
        
        message += f"\nVersion: {revision_entry['version']}\n"
        message += f"Focus: {revision_entry['focus']}\n"
        message += f"Test Coverage: {revision_entry['metrics']['test_coverage']:.1f}%\n"
        
        return message
    
    def _create_git_commit(self, message: str):
        """Create git commit"""
        # Stage all changes
        self._run_command(["git", "add", "-A"])
        
        # Create commit
        self._run_command(["git", "commit", "-m", message])
        
        print("\n📝 Git commit created")
    
    def show_status(self):
        """Show current revision status"""
        current = self.current_revision
        version = self._get_version_for_revision(current)
        focus = self._get_focus_for_revision(current)
        
        start_date = datetime.fromisoformat(self.revision_data["start_date"])
        days_elapsed = (datetime.now() - start_date).days
        days_to_r100 = 100 - current
        
        print("\n" + "="*60)
        print("ArciTEK.AI Revision Status")
        print("="*60)
        print(f"\n📊 Current Revision: r{current}")
        print(f"📦 Current Version: {version}")
        print(f"🎯 Current Focus: {focus}")
        print(f"\n📈 Progress to r100: {current}/100 ({current}%)")
        print(f"📅 Days Elapsed: {days_elapsed}")
        print(f"⏳ Days to r100: ~{days_to_r100}")
        
        metrics = self.revision_data["metrics"]
        print(f"\n🎨 Total Features: {metrics['total_features']}")
        print(f"🐛 Total Bugfixes: {metrics['total_bugfixes']}")
        print(f"⚡ Performance Improvements: {metrics['total_performance_improvements']}")
        print(f"🧪 Test Coverage: {metrics['test_coverage']:.1f}%")
        print(f"🔒 Security Score: {metrics['security_score']}")
        
        # Next milestone
        next_milestone = ((current // 10) + 1) * 10
        revisions_to_milestone = next_milestone - current
        print(f"\n🎯 Next Milestone: r{next_milestone} (in {revisions_to_milestone} revisions)")
        
        print("\n" + "="*60)
    
    def show_plan(self):
        """Show revision plan"""
        current = self.current_revision
        
        print("\n" + "="*60)
        print("ArciTEK.AI Revision Plan")
        print("="*60)
        
        # Show next 10 revisions
        print(f"\n📋 Next 10 Revisions (r{current+1} - r{current+10}):\n")
        
        for i in range(1, 11):
            rev = current + i
            if rev > 100:
                break
            
            version = self._get_version_for_revision(rev)
            focus = self._get_focus_for_revision(rev)
            
            milestone = "🎉 MILESTONE" if rev % 10 == 0 else ""
            print(f"r{rev:3d} | v{version:6s} | {focus:30s} {milestone}")
        
        print("\n" + "="*60)
    
    def generate_report(self):
        """Generate comprehensive revision report"""
        print("\n📊 Generating Revision Report...")
        
        report_file = self.repo_root / "REVISION_REPORT.md"
        
        current = self.current_revision
        version = self._get_version_for_revision(current)
        start_date = datetime.fromisoformat(self.revision_data["start_date"])
        
        report = f"""# ArciTEK.AI Revision Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Current Revision:** r{current}  
**Current Version:** {version}  
**Started:** {start_date.strftime('%Y-%m-%d')}

## Progress Overview

- **Revisions Completed:** {current}/100 ({current}%)
- **Days Elapsed:** {(datetime.now() - start_date).days}
- **Estimated Days to r100:** ~{100 - current}

## Metrics Summary

- **Features Added:** {self.revision_data['metrics']['total_features']}
- **Bugs Fixed:** {self.revision_data['metrics']['total_bugfixes']}
- **Performance Improvements:** {self.revision_data['metrics']['total_performance_improvements']}
- **Test Coverage:** {self.revision_data['metrics']['test_coverage']:.1f}%
- **Security Score:** {self.revision_data['metrics']['security_score']}

## Recent Revisions

"""
        
        # Add last 10 revisions
        recent = self.revision_data["revisions"][-10:]
        for rev in reversed(recent):
            report += f"### r{rev['revision']} - {rev['description']}\n"
            report += f"- **Version:** {rev['version']}\n"
            report += f"- **Category:** {rev['category']}\n"
            report += f"- **Date:** {datetime.fromisoformat(rev['date']).strftime('%Y-%m-%d')}\n"
            report += f"- **Test Coverage:** {rev['metrics']['test_coverage']:.1f}%\n\n"
        
        report += "\n---\n\n*\"Every build is a work of art\"* - infinite♾2025\n"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"✅ Report generated: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description="ArciTEK.AI Automated Revision System"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current revision status"
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show revision plan"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate revision report"
    )
    parser.add_argument(
        "--category",
        choices=["feature", "bugfix", "performance", "security", "documentation", 
                 "testing", "ui", "refactor", "deployment", "automation"],
        help="Revision category"
    )
    parser.add_argument(
        "--description",
        help="Brief description of the revision"
    )
    parser.add_argument(
        "--changes",
        nargs="+",
        help="List of changes"
    )
    
    args = parser.parse_args()
    
    manager = RevisionManager()
    
    if args.status:
        manager.show_status()
    elif args.plan:
        manager.show_plan()
    elif args.report:
        manager.generate_report()
    elif args.category and args.description and args.changes:
        manager.create_revision(args.category, args.description, args.changes)
    else:
        # Interactive mode
        print("\n🎨 ArciTEK.AI Revision Creator")
        print("="*60)
        
        manager.show_status()
        
        print("\n📝 Create New Revision\n")
        
        categories = ["feature", "bugfix", "performance", "security", "documentation",
                     "testing", "ui", "refactor", "deployment", "automation"]
        
        print("Categories:")
        for i, cat in enumerate(categories, 1):
            print(f"  {i}. {cat}")
        
        cat_choice = input("\nSelect category (1-10): ")
        try:
            category = categories[int(cat_choice) - 1]
        except:
            print("Invalid category")
            return
        
        description = input("Brief description: ")
        
        print("\nEnter changes (one per line, empty line to finish):")
        changes = []
        while True:
            change = input("  - ")
            if not change:
                break
            changes.append(change)
        
        if changes:
            manager.create_revision(category, description, changes)
        else:
            print("No changes provided")


if __name__ == "__main__":
    main()
