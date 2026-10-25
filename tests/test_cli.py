"""Unit tests for Institutional Analyst CLI."""
import sys
import io
import pytest
from unittest.mock import patch
import cli


def test_cli_summary(db_session, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "summary", "INE002A01018"]):
        cli.main()
        
    output = buf.getvalue()
    assert "VINIT'S RESEARCH TERMINAL — SECURITY SUMMARY" in output
    assert "INE002A01018" in output
    assert "CODE TEST — SYNTHETIC DATA" in output


def test_cli_dcf(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "dcf", "--fcff", "60.0", "--growth", "0.08", "--wacc", "0.12", "--terminal", "0.04"]):
        cli.main()
        
    output = buf.getvalue()
    assert "DAMODARAN FCFF VALUATION" in output
    assert "919.66" in output


def test_cli_reverse_dcf(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "reverse-dcf", "--ev", "919.6616", "--fcff", "60.0", "--wacc", "0.12", "--terminal", "0.04"]):
        cli.main()
        
    output = buf.getvalue()
    assert "REVERSE DCF IMPLIED GROWTH SOLVER" in output
    assert "8.00%" in output


def test_cli_banking_ddm(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "banking-ddm", "--ni", "1000", "--roe", "0.16", "--growth", "0.05", "--ke", "0.13"]):
        cli.main()
        
    output = buf.getvalue()
    assert "BANKING REGULATORY CAPITAL DDM" in output
    assert "31.25%" in output
    assert "68.75%" in output


def test_cli_regime(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "regime"]):
        cli.main()
        
    output = buf.getvalue()
    assert "INDIAN EQUITY MARKET REGIME" in output
    assert "Nifty 50 Close" in output


def test_cli_tearsheet(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    
    with patch("sys.argv", ["cli.py", "tearsheet", "RELIANCE"]):
        cli.main()
        
    output = buf.getvalue()
    assert "INSTITUTIONAL EQUITY RESEARCH TEARSHEET" in output
    assert "RELIANCE" in output
