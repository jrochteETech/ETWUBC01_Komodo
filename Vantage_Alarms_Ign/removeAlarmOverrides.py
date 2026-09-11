import system


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


def queryOverrideValues(provider, overrideNames):
	query = {
		"options": {
			"includeUdtMembers": True,
			"includeUdtDefinitions": False
		},
		"condition": {
			"attributes": {
				"values": ["override"],
				"requireAll": True
			}
		},
		"returnProperties": list(overrideNames) + ["tagQueryOverrides"]
	}
	return system.tag.query(provider, query)


def groupByParent(results):
	grouped = {}
	for result in results:
		overrides = getOverrides(result)
		if "alarms" not in overrides:
			continue

		fullPath = str(result["fullPath"])
		if "]_types_/" in fullPath:
			continue

		parentPath, tagName = fullPath.rsplit("/", 1)
		config = {"name": tagName}
		for override in overrides:
			if override == "alarms":
				continue
			value = result[override]
			if override == "value":
				value = value.getValue()
			config[override] = value
		grouped.setdefault(parentPath, []).append(config)
	return grouped


def removeAlarmOverrides(provider, dryRun, batchSize):
	alarmOverrideResults = queryAlarmOverrides(provider)
	overrideNames = set()
	for result in alarmOverrideResults:
		overrideNames.update(getOverrides(result))
	results = queryOverrideValues(provider, overrideNames)
	grouped = groupByParent(results)
	total = sum(len(configs) for configs in grouped.values())
	processed = 0
	failed = 0

	print("Alarm overrides found: {}".format(total))
	print("Mode: {}".format("DRY RUN" if dryRun else "APPLY"))

	for parentPath, configs in grouped.items():
		for start in range(0, len(configs), batchSize):
			batch = configs[start:start + batchSize]
			if dryRun:
				for config in batch:
					print("[DRY RUN] {}/{}".format(parentPath, config["name"]))
			else:
				qualities = system.tag.configure(parentPath, batch, "o")
				for config, quality in zip(batch, qualities):
					fullPath = "{}/{}".format(parentPath, config["name"])
					if quality.isGood():
						print("[REMOVED] {}".format(fullPath))
					else:
						failed += 1
						print("[FAILED] {}: {}".format(fullPath, quality))
			processed += len(batch)
			print("Progress: {}/{}".format(processed, total))

	print("=" * 50)
	print("Processed: {}".format(processed))
	print("Failed:    {}".format(failed))

provider = "default"
dryRun = True
batchSize = 100

startTime = system.date.now().getTime()
removeAlarmOverrides(provider, dryRun, batchSize)
endTime = system.date.now().getTime()
print("Total Time: {} s".format((endTime - startTime) / 1000.0))
