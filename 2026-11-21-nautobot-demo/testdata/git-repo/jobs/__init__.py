"""Nautobot Git Repository jobs package."""

from nautobot.apps.jobs import register_jobs

from .lab_inventory_audit import LabInventoryAuditJob

register_jobs(LabInventoryAuditJob)
