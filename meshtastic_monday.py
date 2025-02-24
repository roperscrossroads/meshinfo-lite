from time import strftime, localtime


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
                dt = strftime('%a %b %d %Y', localtime(ts))
                tmp = dict(message)
                tmp["monday"] = dt
                monday.append(tmp)
                uniq = current
        monday = sorted(monday, key=lambda x: x['timestamp'])
        monday.reverse()
        self.monday = monday

    def check_ins(self):
        nodes = {}
        for monday in self.monday:
            frm = monday["from"]
            if frm not in nodes:
                nodes[frm] = {
                    "check_ins": 0,
                    "streak": 0,
                    "mondays": []
                }
            dt = monday["monday"]
            if dt not in nodes[frm]["mondays"]:
                nodes[frm]["mondays"].append(dt)
                nodes[frm]["check_ins"] += 1
        return nodes

    def get_data(self):
        return {
            "messages": self.monday,
            "nodes": self.check_ins()
        }
