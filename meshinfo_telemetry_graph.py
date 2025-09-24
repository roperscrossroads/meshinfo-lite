import matplotlib.pyplot as plt
import datetime
from datetime import timezone
import io
import base64
import json


def draw_graph(telemetry):

    data = {
        "air_util_tx": [],
        "battery_level": [],
        "channel_utilization": [],
        "ts_created": []
    }

    for datapoint in telemetry:
        for key in data:
            data[key].append(datapoint[key])

    # Convert ts_created to datetime format
    time_stamps = [
        datetime.datetime.fromtimestamp(int(t), tz=timezone.utc) for t in data["ts_created"]
    ]

    # Create the plot
    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Plot air_util_tx and channel_utilization on left y-axis
    ax1.set_xlabel("Time")
    ax1.set_ylabel(
        "Air Util TX / Channel Utilization / Battery Level",
        color="tab:blue"
    )
    ax1.plot(
        time_stamps,
        data["air_util_tx"],
        label="Air Util TX",
        marker="o",
        color="tab:blue"
    )
    ax1.plot(
        time_stamps,
        data["channel_utilization"],
        label="Channel Utilization",
        marker="s",
        linestyle="dashed",
        color="tab:purple"
    )
    ax1.plot(
        time_stamps,
        data["battery_level"],
        label="Battery Level",
        marker="^",
        linestyle="dotted",
        color="tab:red"
    )
    ax1.tick_params(axis="y", labelcolor="tab:blue")

    plt.title("24hr Telemetry Data")
    fig.tight_layout()
    ax1.legend(loc="upper left")
    # Save the plot to a BytesIO buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)

    # Encode image to Base64
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Print Base64 output (or return it from a function)
    return img_base64
