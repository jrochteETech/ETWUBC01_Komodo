# Run this script in the Ignition Designer Script Console.
# It finds UDT definitions that have instances, then returns alarms from only
# those UDT definitions.

import system
from java.lang import String as JString
from java.nio.charset import Charset


def getRelativeTypePath(provider, typeId):
    typePath = str(typeId)
    definitionPrefix = "[{}]_types_/".format(provider)

    if typePath.startswith(definitionPrefix):
        return typePath[len(definitionPrefix):]

    return typePath.lstrip("/")


def findUsedUDTs(provider):
    query = {
        "options": {
            "includeUdtMembers": True,
            "includeUdtDefinitions": False
        },
        "condition": {
            "tagType": "UdtInstance",
            "attributes": {
                "values": [],
                "requireAll": True
            }
        },
        "returnProperties": [
            "typeId"
        ]
    }

    results = system.tag.query(provider, query)
    usedUDTs = set()

    for result in results:
        usedUDTs.add(getRelativeTypePath(provider, result["typeId"]))

    return sorted(usedUDTs)


def getUsedUDTAlarms(provider, usedUDTs):
    query = {
        "options": {
            "includeUdtMembers": True,
            "includeUdtDefinitions": True
        },
        "condition": {
            "path": "*_types_*",
            "attributes": {
                "values": [
                    "alarm"
                ],
                "requireAll": True
            }
        },
        "returnProperties": [
            "alarms",
            "tagType"
        ]
    }

    results = system.tag.query(provider, query)
    alarmsByUDT = {}

    for result in results:
        alarmPath = str(result["fullPath"]).rsplit("]_types_/", 1)[-1]

        for udtPath in usedUDTs:
            if alarmPath == udtPath or alarmPath.startswith(udtPath + "/"):
                alarmsByUDT.setdefault(udtPath, []).append({
                    "tagPath": alarmPath,
                    "tagType": result.get("tagType", ""),
                    "alarms": result["alarms"]
                })
                break

    return alarmsByUDT


def csvEscape(value):
    text = u"{}".format(value if value is not None else "")
    return u'"{}"'.format(text.replace(u'"', u'""'))


def getAlarmValue(alarm, key, defaultValue):
    value = alarm.get(key)
    if hasattr(value, "keys") and "value" in value:
        value = value.get("value")
    if value is None or value == "":
        return defaultValue
    return value


def exportAlarms(alarmsByUDT, outputPath):
    columns = [
        "UDT Path",
        "Path",
        "Tag Type",
        "AlarmIndex",
        "AlarmName",
        "Label",
        "Priority",
        "Mode",
        "SetpointA",
        "Enabled",
        "RawAlarm"
    ]
    lines = [u",".join([csvEscape(column) for column in columns])]

    for udtPath in sorted(alarmsByUDT.keys()):
        for alarmTag in alarmsByUDT[udtPath]:
            for alarmIndex, alarm in enumerate(alarmTag["alarms"]):
                lines.append(u",".join([
                    csvEscape(udtPath),
                    csvEscape(alarmTag["tagPath"]),
                    csvEscape(alarmTag["tagType"]),
                    csvEscape(alarmIndex),
                    csvEscape(getAlarmValue(alarm, "name", "")),
                    csvEscape(getAlarmValue(alarm, "label", "")),
                    csvEscape(getAlarmValue(alarm, "priority", "Low")),
                    csvEscape(getAlarmValue(alarm, "mode", "Equal")),
                    csvEscape(getAlarmValue(alarm, "setpointA", "0")),
                    csvEscape(getAlarmValue(alarm, "enabled", "True")),
                    csvEscape(alarm)
                ]))

    csvText = u"\r\n".join(lines) + u"\r\n"
    utf8 = Charset.forName("UTF-8")
    system.file.writeFile(outputPath, JString(csvText).getBytes(utf8))
    
    return outputPath


theProvider = "default"
timestamp = system.date.format(system.date.now(), "yyyyMMddHHmmss")
theOutputPath = r"C:\AlarmReports\{}_used_udt_alarms_{}.csv".format(theProvider, timestamp)

usedUDTs = findUsedUDTs(theProvider)
alarmsByUDT = getUsedUDTAlarms(theProvider, usedUDTs)
alarmTagCount = sum([len(alarmTags) for alarmTags in alarmsByUDT.values()])
alarmCount = sum([
    len(alarmTag["alarms"])
    for alarmTags in alarmsByUDT.values()
    for alarmTag in alarmTags
])

print("-" * 25)
print("Used UDTs Found: {}".format(len(usedUDTs)))
print("Used UDTs with Alarms: {}".format(len(alarmsByUDT)))
print("Alarm Tags Found: {}".format(alarmTagCount))
print("Total Alarms Found: {}".format(alarmCount))
print("-" * 25)

outputPath = exportAlarms(alarmsByUDT, theOutputPath)
print("CSV written to: {}".format(outputPath))