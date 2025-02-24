from time import strftime, localtime
from datetime import datetime, timedelta
import json


class MeshtasticMonday:
    def __init__(self, data):
        monday = []
        uniq = ""
        for channel in data.chat["channels"]:
            for message in data.chat["channels"][channel]["messages"]:
                to = message["to"]
                if (to != "ffffffff"):
                    continue
                ts = message["timestamp"]
                day = strftime('%w', localtime(ts))
                if day != "1":
                    continue
                text = message["text"]
                if "meshtasticmonday" not in text.lower():
                    continue
                frm = message["from"]
                current = frm + "." + text
                if current == uniq:
                    continue
                dt = str(datetime.fromtimestamp(ts).date())
                tmp = dict(message)
                tmp["monday"] = dt
                monday.append(tmp)
                uniq = current
        monday = sorted(monday, key=lambda x: x['timestamp'])
        self.monday = monday

    def check_ins(self):
        nodes = {}
        if not self.monday:
            return nodes
        for monday in self.monday:
            frm = monday["from"]
            if frm not in nodes:
                nodes[frm] = {
                    "check_ins": 0,
                    "streak": 1,
                    "mondays": []
                }
            dt = monday["monday"]
            mondays = nodes[frm]["mondays"]
            if dt not in mondays:
                nodes[frm]["mondays"].append(dt)
                nodes[frm]["check_ins"] += 1

        #  Calculate streak
        latest_monday = self.monday[-1]["monday"]
        for node in nodes:
            mondays = list(nodes[node]["mondays"])
            if latest_monday not in mondays:
                nodes[node]["streak"] = 0
                continue
            for monday in mondays:
                dto = datetime.strptime(monday, '%Y-%m-%d')
                lastweek = str((dto.date() - timedelta(days=7)))
                if lastweek in mondays:
                    nodes[node]["streak"] += 1
                else:
                    nodes[node]["streak"] = 0
        return nodes

    def get_data(self):
        rev = list(self.monday)
        rev.reverse()
        return {
            "messages": rev,
            "nodes": self.check_ins()
        }
