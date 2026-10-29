"""
Render a clean, professional, high-resolution ERD diagram for Laura's Task 2.
"""
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
docs_dir = os.path.join(base_dir, "docs")
os.makedirs(docs_dir, exist_ok=True)
out_png = os.path.join(docs_dir, "erd_diagram.png")

fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
ax.set_facecolor("#f8fafc")
fig.patch.set_facecolor("#ffffff")
ax.axis("off")

# Title and subtitle
ax.text(7, 7.5, "Entity Relationship Diagram (ERD) - PJME Energy Relational Schema", 
        fontsize=16, fontweight="bold", ha="center", color="#0f172a")
ax.text(7, 7.15, "3-Table Normalized Relational Architecture for Time Series Database (MySQL / PostgreSQL)", 
        fontsize=11, fontstyle="italic", ha="center", color="#475569")

def draw_table(ax, x, y, width, height, title, columns, header_bg="#1e293b"):
    # Header box
    hdr_h = 0.55
    hdr = patches.FancyBboxPatch((x, y + height - hdr_h), width, hdr_h,
                                 boxstyle="round,pad=0.02,rounding_size=0.08",
                                 facecolor=header_bg, edgecolor="none")
    ax.add_patch(hdr)
    ax.text(x + width/2, y + height - hdr_h/2, title, 
            fontsize=12, fontweight="bold", color="#ffffff", ha="center", va="center")
    
    # Body box
    body = patches.FancyBboxPatch((x, y), width, height - hdr_h,
                                  boxstyle="round,pad=0.02,rounding_size=0.08",
                                  facecolor="#ffffff", edgecolor="#cbd5e1", linewidth=1.5)
    ax.add_patch(body)
    
    # Draw columns
    line_y = y + height - hdr_h - 0.35
    for is_pk, name, data_type in columns:
        badge = "[PK]" if is_pk == "PK" else ("[FK]" if is_pk == "FK" else "    ")
        b_color = "#b91c1c" if is_pk == "PK" else ("#0369a1" if is_pk == "FK" else "#64748b")
        
        ax.text(x + 0.2, line_y, badge, fontsize=9, fontweight="bold", color=b_color, va="center")
        ax.text(x + 0.9, line_y, name, fontsize=9.5, fontweight="semibold", color="#1e293b", va="center")
        ax.text(x + width - 0.2, line_y, data_type, fontsize=8.5, color="#64748b", ha="right", va="center")
        line_y -= 0.32

# Table 1: DATA_SOURCES
data_sources_cols = [
    ("PK", "source_id", "INT AUTO_INCREMENT"),
    ("", "dataset_name", "VARCHAR(150) NOT NULL"),
    ("", "provider", "VARCHAR(150) NOT NULL"),
    ("", "source_url", "VARCHAR(500)"),
    ("", "description", "TEXT")
]
draw_table(ax, 0.8, 3.2, 3.6, 2.5, "DATA_SOURCES", data_sources_cols, header_bg="#0f766e")

# Table 2: ENERGY_READINGS
energy_readings_cols = [
    ("PK", "reading_id", "BIGINT AUTO_INCREMENT"),
    ("FK", "Datetime", "DATETIME NOT NULL (UNIQUE)"),
    ("", "PJME_MW", "DOUBLE NOT NULL"),
    ("", "temperature_c", "DOUBLE NOT NULL"),
    ("", "was_imputed", "BOOLEAN NOT NULL DEFAULT 0"),
    ("FK", "source_id", "INT NOT NULL"),
    ("", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
]
draw_table(ax, 5.0, 2.3, 4.2, 3.6, "ENERGY_READINGS (Multivariate Fact)", energy_readings_cols, header_bg="#1e3a8a")


# Table 3: TIME_DIMENSIONS
time_dimensions_cols = [
    ("PK", "Datetime", "DATETIME NOT NULL"),
    ("", "hour", "TINYINT UNSIGNED NOT NULL"),
    ("", "day_of_week", "TINYINT UNSIGNED NOT NULL"),
    ("", "month", "TINYINT UNSIGNED NOT NULL"),
    ("", "is_weekend", "BOOLEAN NOT NULL")
]
draw_table(ax, 9.8, 3.2, 3.6, 2.5, "TIME_DIMENSIONS (Dimension)", time_dimensions_cols, header_bg="#6d28d9")

# Connectors and Crow's Foot relations
# 1. DATA_SOURCES (1) ---> (N) ENERGY_READINGS
ax.annotate("", xy=(5.0, 4.3), xytext=(4.4, 4.3),
            arrowprops=dict(arrowstyle="->", lw=2, color="#0f766e"))
ax.text(4.45, 4.45, "1", fontsize=11, fontweight="bold", color="#0f766e")
ax.text(4.85, 4.45, "N", fontsize=11, fontweight="bold", color="#0f766e")
ax.text(4.7, 4.05, "supplies", fontsize=9, color="#0f766e", ha="center")

# 2. TIME_DIMENSIONS (1) ---> (1) ENERGY_READINGS
ax.annotate("", xy=(9.2, 4.3), xytext=(9.8, 4.3),
            arrowprops=dict(arrowstyle="->", lw=2, color="#6d28d9"))
ax.text(9.7, 4.45, "1", fontsize=11, fontweight="bold", color="#6d28d9")
ax.text(9.25, 4.45, "1 (Unique)", fontsize=9.5, fontweight="bold", color="#6d28d9")
ax.text(9.5, 4.05, "describes", fontsize=9, color="#6d28d9", ha="center")


# Key / Constraints box
legend_box = patches.FancyBboxPatch((1.5, 0.6), 11.0, 1.4,
                                    boxstyle="round,pad=0.03,rounding_size=0.08",
                                    facecolor="#f1f5f9", edgecolor="#94a3b8", linewidth=1)
ax.add_patch(legend_box)
ax.text(1.8, 1.65, "Architectural & Integrity Highlights:", fontsize=10.5, fontweight="bold", color="#0f172a")
notes = [
    "• Referential Integrity: energy_readings.Datetime -> time_dimensions.Datetime (ON DELETE CASCADE, ON UPDATE CASCADE)",
    "• Provenance Tracking: energy_readings.source_id -> data_sources.source_id (ON DELETE RESTRICT)",
    "• Dimension Pre-indexing: Calendar attributes (hour, day_of_week, month, is_weekend) indexed for O(1) seasonal & diurnal aggregation",
    "• Normalization: Avoids repeating static time attributes across 145,362 hourly readings; strictly enforces 3NF."
]
y_note = 1.38
for n in notes:
    ax.text(1.8, y_note, n, fontsize=8.8, color="#334155")
    y_note -= 0.22

ax.set_xlim(0, 14)
ax.set_ylim(0, 8)
plt.tight_layout()
plt.savefig(out_png, dpi=300, bbox_inches="tight")
plt.close()

print("ERD diagram rendered to:", out_png)
