import system
from java.lang import String as JString
from java.nio.charset import Charset


def csvEscape(value):
	text = u"{}".format(value if value is not None else "")
	return u'"{}"'.format(text.replace(u'"', u'""'))


def exportResults(rows, outputPath):
	columns = ["timestamp", "provider", "mode", "tagPath", "status", "details"]
	lines = [u",".join([csvEscape(column) for column in columns])]
	for row in rows:
		lines.append(u",".join([csvEscape(row.get(column, "")) for column in columns]))

	csvText = u"\r\n".join(lines) + u"\r\n"
	utf8 = Charset.forName("UTF-8")
	system.file.writeFile(outputPath, JString(csvText).getBytes(utf8))
	print("CSV results written to: {}".format(outputPath))
	return outputPath


def queryAlarmOverrides(provider):
	query = {
		"options": {
			"includeUdtMembers": True,
			"includeUdtDefinitions": False
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
			"tagQueryOverrides"
		]
	}
	results = system.tag.query(provider, query)
	return [result for result in results if "alarms" in getOverrides(result)]


def getOverrides(result):
	return [item.strip() for item in str(result["tagQueryOverrides"]).split(",")]


def getConfigurationIndex(provider):
	configByPath = {}

	def addConfigs(configs, parentPath):
		for sourceConfig in configs:
			config = dict(sourceConfig)
			tagName = str(config.get("name", ""))
			separator = "" if parentPath.endswith("]") else "/"
			fullPath = "{}{}{}".format(parentPath, separator, tagName)
			configByPath[fullPath] = config
			addConfigs(config.get("tags", []), fullPath)

	providerPath = "[{}]".format(provider)
	addConfigs(system.tag.getConfiguration(providerPath, True), providerPath)
	return configByPath


def buildOverrideConfigs(results, configByPath):
	overrideConfigs = []
	missingPaths = []
	for result in results:
		fullPath = str(result["fullPath"])
		if "]_types_/" in fullPath:
			continue

		parentPath, tagName = fullPath.rsplit("/", 1)
		sourceConfig = configByPath.get(fullPath)
		if sourceConfig is None:
			missingPaths.append(fullPath)
			continue
		config = dict(sourceConfig)
		config["name"] = tagName
		config.pop("alarms", None)
		config.pop("path", None)
		config.pop("tags", None)
		overrideConfigs.append({
			"parentPath": parentPath,
			"fullPath": fullPath,
			"config": config
		})
	return overrideConfigs, missingPaths


def removeAlarmOverrides(provider, DRY_RUN, outputPath):
	alarmOverrideResults = queryAlarmOverrides(provider)
	configByPath = getConfigurationIndex(provider)
	overrideConfigs, missingPaths = buildOverrideConfigs(alarmOverrideResults, configByPath)
	total = len(overrideConfigs)
	processed = 0
	failed = 0
	auditRows = []
	mode = "DRY RUN" if DRY_RUN else "APPLY"

	print("Alarm overrides found: {}".format(total))
	print("Configurations not found: {}".format(len(missingPaths)))
	for missingPath in missingPaths:
		print("[SKIPPED] Configuration not found: {}".format(missingPath))
	print("Mode: {}".format(mode))

	for overrideConfig in overrideConfigs:
		parentPath = overrideConfig["parentPath"]
		fullPath = overrideConfig["fullPath"]
		config = overrideConfig["config"]
		if DRY_RUN:
			print("[DRY RUN] {}".format(fullPath))
			auditRows.append({
				"timestamp": system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss.SSS"),
				"provider": provider,
				"mode": mode,
				"tagPath": fullPath,
				"status": "WOULD_REMOVE",
				"details": "Alarm override would be removed"
			})
		else:
			quality = system.tag.configure(parentPath, [config], "o")[0]
			if quality.isGood():
				status = "REMOVED"
				print("[REMOVED] {}".format(fullPath))
			else:
				status = "FAILED"
				failed += 1
				print("[FAILED] {}: {}".format(fullPath, quality))
			auditRows.append({
				"timestamp": system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss.SSS"),
				"provider": provider,
				"mode": mode,
				"tagPath": fullPath,
				"status": status,
				"details": str(quality)
			})
		processed += 1
		print("Progress: {}/{}".format(processed, total))

	print("=" * 50)
	print("Processed: {}".format(processed))
	print("Failed:    {}".format(failed))
	exportResults(auditRows, outputPath)


provider = "default"
DRY_RUN = True
timestamp = system.date.format(system.date.now(), "yyyyMMddHHmmss")
outputPath = r"C:\AlarmReports\{}_alarm_override_removal_results_{}.csv".format(provider, timestamp)

startTime = system.date.now().getTime()
removeAlarmOverrides(provider, DRY_RUN, outputPath)
endTime = system.date.now().getTime()
print("Total Time: {} s".format((endTime - startTime) / 1000.0))