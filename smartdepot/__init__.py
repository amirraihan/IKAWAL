"""SmartDepot — Banduan Dagang Monitoring & Decision Support.

A monitoring system for foreign detainees (*banduan dagang*) under remand,
built on the BPK / Iringkawal reman register.

Use cases
---------
UC-1  Interactive Monitoring Dashboard (with data entry)
UC-2  Case Decision Support  (automated reman + risk priority + recommendation)
UC-3  AI Depot Population Forecasting
UC-4  AI Insight & Automated Report Generator

Solution elements
-----------------
E1  Data entry & ingestion      E6  Risk scoring
E2  Store & event log           E7  Decision support
E3  Feature layer               E8  Population forecaster
E4  Interactive dashboard       E9  Insight & report generator
E5  Reman engine                E10 Audit, access & exports
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
