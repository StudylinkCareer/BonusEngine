import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import MasterAgent
from sqlalchemy import text

# First add missing columns if needed
with engine.connect() as conn:
    for col, col_type in [
        ("triggers_master_agent_rate", "BOOLEAN DEFAULT FALSE"),
        ("notes", "VARCHAR(300)"),
    ]:
        result = conn.execute(text(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_name='ref_master_agents' AND column_name='{col}'"
        ))
        if not result.fetchone():
            conn.execute(text(f"ALTER TABLE ref_master_agents ADD COLUMN {col} {col_type}"))
            conn.commit()
            print(f"✅ Added '{col}' column to ref_master_agents")
        else:
            print(f"⏭  ref_master_agents.{col} already exists")

db = SessionLocal()
deleted = db.query(MasterAgent).delete()
db.commit()
print(f"\nCleared {deleted} existing master agents\n")

# Source: Classification_of_master-agent_and_group.pdf
# Master Agents trigger: (1) CO Sub rate table, (2) 0.7 KPI weight, (3) IsPartnerCase flag
# Groups are institutions — do NOT trigger master-agent logic

MASTER_AGENTS = [
    {"agent_name": "Acknowledge Education",         "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": ""},
    {"agent_name": "Adventus",                      "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "Out-system via Adventus"},
    {"agent_name": "Amerigo Education LLC",         "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "US specialist"},
    {"agent_name": "ApplyBoard",                    "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "Also listed as 'Apply Board'"},
    {"agent_name": "Can-Achieve",                   "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "Also listed as 'Can-Achieve'"},
    {"agent_name": "EC English",                    "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Education Centre of Australia (ECA)", "agent_type": "GROUP",  "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Educatius US",                  "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "US specialist"},
    {"agent_name": "EduCo International Group",     "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": ""},
    {"agent_name": "ELS",                           "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "FLS International",             "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "GEEBEE Education",              "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "Also appears as 'GEEBEE'"},
    {"agent_name": "Golden Education (GE)",         "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True,  "notes": "Also appears as 'GE'"},
    {"agent_name": "ILAC",                          "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "INTO",                          "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "InUni",                         "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Kaplan",                        "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Kings Education",               "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Lightpath Group",               "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Link2Uni",                      "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Navitas",                       "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution — NOT master agent"},
    {"agent_name": "Raffles Education Network",     "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Shorelight Education",          "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Study Group",                   "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Universal Learning Group",      "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "UP Education",                  "agent_type": "GROUP",        "triggers_master_agent_rate": False, "notes": "Institution group"},
    {"agent_name": "Wellspring International Education", "agent_type": "MASTER_AGENT", "triggers_master_agent_rate": True, "notes": "Also appears as 'Wellspring'"},
]

for agent in MASTER_AGENTS:
    db.add(MasterAgent(
        agent_name=agent["agent_name"],
        agent_type=agent["agent_type"],
        is_active=True,
        notes=agent["notes"],
        triggers_master_agent_rate=agent["triggers_master_agent_rate"],
    ))

db.commit()
print(f"✅ Loaded {len(MASTER_AGENTS)} master agents/groups successfully!")
print(f"\nReminder:")
print(f"  - Master Agents trigger: CO Sub rate table, 0.7 KPI weight, IsPartnerCase flag")
print(f"  - Groups are institutions — do NOT trigger master-agent logic")
db.close()
