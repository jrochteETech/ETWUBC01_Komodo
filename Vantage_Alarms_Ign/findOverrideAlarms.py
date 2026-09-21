import system
from java.lang import String as JString
from java.nio.charset import Charset


MISSING = object()


def compareAlarmConfig(instanceValue, definitionValue, definitionKey=None, keyValue=MISSING):
	differences = []
	instanceIsMap = hasattr(instanceValue, "keys")
	definitionIsMap = hasattr(definitionValue, "keys")

	if instanceIsMap and definitionIsMap:
		for key in sorted(definitionValue.keys(), key=lambda item: str(item)):
			instanceChild = instanceValue.get(key, MISSING)
			definitionChild = definitionValue.get(key)
			childKey = definitionKey if definitionKey is not None else str(key)
			childKeyValue = keyValue if definitionKey is not None else instanceChild
			differences.extend(compareAlarmConfig(
				instanceChild,
				definitionChild,
				childKey,
				childKeyValue
			))
		return differences

	instanceIsList = isinstance(instanceValue, (list, tuple))
	definitionIsList = isinstance(definitionValue, (list, tuple))
	if instanceIsList and definitionIsList:
		for index in range(len(definitionValue)):
			instanceChild = instanceValue[index] if index < len(instanceValue) else MISSING
			definitionChild = definitionValue[index]
			differences.extend(compareAlarmConfig(
				instanceChild,
				definitionChild,
				definitionKey,
				keyValue
			))
		if len(instanceValue) != len(definitionValue):
			differences.append((
				definitionKey if definitionKey is not None else "alarms",
				keyValue if definitionKey is not None else instanceValue
			))
		return differences

	if instanceValue is MISSING or instanceValue != definitionValue:
		differences.append((
			definitionKey if definitionKey is not None else "alarms",
			keyValue if definitionKey is not None else instanceValue
		))
	return differences


def formatAlarmValue(value):
	if value is MISSING:
		return "<missing>"
	if hasattr(value, "keys") and "value" in value:
		value = value.get("value")
	return u"{}".format(value if value is not None else "<null>").replace("\r", "\\r").replace("\n", "\\n")


def csvEscape(value):
	text = u"{}".format(value if value is not None else "")
	return u'"{}"'.format(text.replace(u'"', u'""'))


def exportResults(rows, outputPath):
	differenceColumns = sorted(set([
		key
		for row in rows
		for key in row.get("differences", {}).keys()
	]))
	columns = ["message", "tagPath", "typeid"] + differenceColumns
	lines = [u",".join([csvEscape(column) for column in columns])]
	for row in rows:
		values = [row.get(column, "") for column in columns[:3]]
		values.extend([
			row.get("differences", {}).get(column, "")
			for column in differenceColumns
		])
		lines.append(u",".join([csvEscape(value) for value in values]))

	csvText = u"\r\n".join(lines) + u"\r\n"
	utf8 = Charset.forName("UTF-8")
	system.file.writeFile(outputPath, JString(csvText).getBytes(utf8))
	return outputPath


def getOverrides(result):
	return [item.strip() for item in str(result["tagQueryOverrides"]).split(",")]


def queryAllOverrides(provider):
	query = {
		"options": {
			"includeUdtMembers": True,
			"includeUdtDefinitions": True
		},
		"condition": {
			"attributes": {
				"values": [
					"override"
				],
				"requireAll": True
			}
		},
		"returnProperties": [
			"alarms",
			"tagQueryOverrides"
		]
	}
	
	results = system.tag.query(provider, query)
	returnMe = []
	for each in results:
		if "alarms" not in getOverrides(each):
			continue
		returnMe.append([
			each['fullPath'],
			each['alarms']
		])
	return returnMe


def queryAllUDTAlarms(provider):
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
	returnMe = {}
	for each in results:
		returnMe[str(each['fullPath']).rsplit("]_types_/")[-1]] = each['alarms']
	return returnMe


def gettypeid(provider, tagPath, udtInstances, configCache):
	segments = tagPath.strip('/').split('/')

	for i in range(len(segments) - 1):
		instancePath = "/".join(segments[:i+1])
		if instancePath in udtInstances:
			return udtInstances[instancePath], tagPath[len(instancePath):]

		currentPath = "["+provider+"]" + instancePath

		if currentPath not in configCache:
			configCache[currentPath] = system.tag.getConfiguration(currentPath, False)
		config = configCache[currentPath]

		if config and len(config) > 0:
			tagType = config[0].get('tagType', '')
			
			# UDT instances report tagType as "UdtInstance"
			if str(tagType) == 'UdtInstance':
				typeID = config[0].get('typeId','')
				udtInstances[instancePath] = typeID
				return typeID, tagPath[len(instancePath):]
	return None


def main(provider, outputPath):
	startTime = system.date.now().getTime()
	placeCount = 0
	instanceAlarmCount = 0
	missMatchingAlarms = []
	udtInstances = {}
	configCache = {}

	allUDTAlarms = queryAllUDTAlarms(provider)
	print("UDT alarm Definitions: " + str(len(allUDTAlarms)))
	allOverrides = queryAllOverrides(provider)
	print("Tag Alarm Overrides: " + str(len(allOverrides)))

	for each in allOverrides:
		placeCount += 1
		if placeCount % 100 == 0:
			print(str(placeCount)+ "/" + str(len(allOverrides)))
		
		tagPath = str(each[0]).rsplit("]")[-1]
		typeInfo = gettypeid(provider, tagPath, udtInstances, configCache)
		
		overrideAlarm = each[1]
		if typeInfo is not None:
			typeID, relPath = typeInfo
			udtAlarmPath = typeID+relPath
			if udtAlarmPath not in allUDTAlarms:
				instanceAlarmCount += 1
				missMatchingAlarms.append(
					{
						"message": "Alarm definition not found: " + udtAlarmPath,
						"tagPath": tagPath,
						"typeid": typeID
					}
				)
			elif overrideAlarm != allUDTAlarms[udtAlarmPath]:
				differenceValues = {}
				for key, value in compareAlarmConfig(
					overrideAlarm,
					allUDTAlarms[udtAlarmPath]
				):
					formattedValue = formatAlarmValue(value)
					values = differenceValues.setdefault(key, [])
					if formattedValue not in values:
						values.append(formattedValue)
				differences = dict([
					(key, "; ".join(values))
					for key, values in differenceValues.items()
				])
				missMatchingAlarms.append(
					{
						"message": "Alarm config differs",
						"tagPath": tagPath,
						"typeid": typeID,
						"differences": differences
					}
				)
		else:
			instanceAlarmCount += 1
			missMatchingAlarms.append(
				{
					"message": "UDT instance/type not found",
					"tagPath": tagPath,
					"typeid": ""
				}
				)
	#	print(each)
		
	endTime = system.date.now().getTime()
	outputPath = exportResults(missMatchingAlarms, outputPath)

	print("="*50)

	print("Miss Matched Alarms: " + str(len(missMatchingAlarms)))
	print("Alarms not in UDTs: " + str(instanceAlarmCount))
	print("Total Time:           {} s".format((endTime - startTime)/1000))
	if outputPath is not None:
		print("CSV exported to:      " + outputPath)

provider = "default"
timestamp = system.date.format(system.date.now(), "yyyyMMddHHmmss")
outputPath = r"C:\AlarmReports\{}_alarm_override_results_{}.csv".format(provider, timestamp)
main(provider, outputPath)