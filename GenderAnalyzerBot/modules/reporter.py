import matplotlib.pyplot as plt
import os
from modules.database import db

class Reporter:
    def __init__(self):
        self.output_dir = "outputs"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_report(self, chat_id, chat_title):
        """Statistika va diagramma yaratish"""
        stats = db.get_stats(chat_id)
        
        # Ma'lumotlarni tartibga solish
        labels = []
        sizes = []
        colors = []
        
        gender_map = {
            'Male': {'label': 'Erkaklar', 'color': '#3498db'},
            'Female': {'label': 'Ayollar', 'color': '#e74c3c'},
            'Deleted': {'label': 'O\'chirilganlar', 'color': '#34495e'},
            'Unknown': {'label': 'Aniqlanmagan', 'color': '#95a5a6'}
        }

        total = sum(stats.values())
        if total == 0:
            return "Ma'lumotlar topilmadi.", None

        for gender, count in stats.items():
            info = gender_map.get(gender, gender_map['Unknown'])
            labels.append(f"{info['label']} ({count})")
            sizes.append(count)
            colors.append(info['color'])

        # Diagramma yaratish
        plt.figure(figsize=(10, 7))
        explode = [0.05] * len(sizes)
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, explode=explode)
        plt.title(f"Gender Analizi: {chat_title}\nJami a'zolar: {total}")
        
        file_path = os.path.join(self.output_dir, f"report_{chat_id}.png")
        plt.savefig(file_path)
        plt.close()

        # Matnli hisobot
        text_report = f"📊 **{chat_title} uchun Gender Analizi:**\n\n"
        for gender, count in stats.items():
            label = gender_map.get(gender, gender_map['Unknown'])['label']
            percent = (count / total) * 100
            text_report += f"- {label}: {count} ta ({percent:.1f}%)\n"
        
        text_report += f"\nTotal: {total}"
        
        return text_report, file_path

reporter = Reporter()
