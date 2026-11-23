# Version history:
# V1 - Applies keep, delete, and priority-change actions from a CSV file.
# V2 - Adds priority/label reporting, medium-priority validation, and custom-email cleanup.
# V3 - Adds optional alarm-label updates and summary counters for changed fields.
# V4 - Removes priority/label overrides from selected UDT-definition alarms.
# Run in Ignition's Script Console. CSV columns: path,alarmName.
# Paths are relative to [PROVIDER]_types_ (for example, DerivedUDT/Status).
# Use on alarms inherited from a parent UDT; base alarms revert to defaults.
# Other alarm properties and tag configuration are preserved. DRY_RUN defaults to True.
# Remaining overridden properties keep the alarm overridden.

import system
from java.lang import String as JString
from java.nio.charset import Charset

def choose_file():
    path = system.file.openFile("csv", "CSV Files (*.csv)|*.csv|All Files (*.*)|*.*")
    if path is None:
        print("[CANCELLED] No file selected.")
    else:
        print("[FILE] Selected: {}".format(path))
    return path


def build_output_path(input_path):
    normalised = input_path.replace("\\", "/")
    folder     = normalised.rsplit("/", 1)[0]
    filename   = normalised.rsplit("/", 1)[-1]
    timestamp  = system.date.format(system.date.now(), "yyyyMMddHHmmss")
    if "." in filename:
        base, ext = filename.rsplit(".", 1)
        out_name  = "{}_results_{}.{}".format(base, timestamp, ext)
    else:
        out_name  = "{}_results.csv".format(filename)
    return "{}/{}".format(folder, out_name)


def bytes_to_unicode(raw):
    utf8   = Charset.forName("UTF-8")
    latin1 = Charset.forName("ISO-8859-1")
    try:
        text = unicode(JString(raw, utf8))
    except Exception:
        text = unicode(JString(raw, latin1))
    if text.startswith(u"\ufeff"):
        text = text[1:]
    return text


def parse_csv_unicode(text):
    text = text.replace(u"\r\n", u"\n").replace(u"\r", u"\n").rstrip(u"\n")
    rows      = []
    row       = []
    field     = []
    in_quotes = False
    i         = 0
    while i < len(text):
        ch = text[i]
        if in_quotes:
            if ch == u'"':
                if i + 1 < len(text) and text[i + 1] == u'"':
                    field.append(u'"')
                    i += 2
                    continue
                else:
                    in_quotes = False
            else:
                field.append(ch)
        else:
            if ch == u'"':
                in_quotes = True
            elif ch == u',':
                row.append(u"".join(field))
                field = []
            elif ch == u'\n':
                row.append(u"".join(field))
                field = []
                rows.append(row)
                row = []
            else:
                field.append(ch)
        i += 1
    if field or row:
        row.append(u"".join(field))
        rows.append(row)
    return rows


def read_decisions(provider, path):
    raw_bytes = system.file.readFileAsBytes(path)
    text      = bytes_to_unicode(raw_bytes)
    rows      = parse_csv_unicode(text)
    if not rows:
        print("  [WARN] CSV file appears to be empty.")
        return [], []
    header_row = [h.strip().lower() for h in rows[0]]
    def col(name):
        try:
            return header_row.index(name.lower())
        except ValueError:
            return None
    idx_path   = col("path")
    idx_name   = col("alarmname")
    missing_headers = []
    if idx_path   is None: missing_headers.append("path")
    if idx_name   is None: missing_headers.append("alarmName")
    if missing_headers:
        print("  [ERROR] CSV is missing required header column(s): {}".format(", ".join(missing_headers)))
        return [], []
    decisions = []
    skipped   = []

    def get(row, idx):
        if idx is None or idx >= len(row):
            return u""
        return row[idx].strip()

    for i, row in enumerate(rows[1:], start=2):
        path_   = get(row, idx_path)
        name    = get(row, idx_name)
        errors = []
        record = {
            "path":        path_,
            "alarmName":   name,
            "status":      u"",
            "message":     u"",
            "priorityChanged": False,
            "labelChanged": False,
        }

        if not path_:
            errors.append("Missing Path")
        if not name:
            errors.append("Missing AlarmName")
        if path_ and (path_.startswith("[") or path_.startswith("_types_/") or
                      path_.startswith("/") or path_.endswith("/") or
                      any(part in ("", ".", "..") for part in path_.split("/"))):
            errors.append("Path must be relative to [{}]_types_".format(provider))

        if errors:
            error_msg = u", ".join(errors)
            print(u"  [SKIP] Row {}: {} | Errors: {}".format(i, path_, error_msg))
            record["status"]  = u"SKIPPED"
            record["message"] = error_msg
            skipped.append(record)
            continue

        decisions.append(record)
    return decisions, skipped


def apply_decision(decision, current, total, dry_run, provider):
    tag_path   = "[" + provider + "]_types_/" + decision["path"]
    alarm_name = decision["alarmName"]
    print(u"\n[{}/{}] [{}] {}  |  Alarm: '{}'".format(
        current,
        total,
        "DRY RUN" if dry_run else "APPLY",
        tag_path,
        alarm_name
    ))
    def set_result(status, message):
        decision["status"]  = status
        decision["message"] = message
        print(u"  [{}] {}".format(status, message))
    try:
        config = system.tag.getConfiguration(tag_path, False)
        if not config:
            set_result("ERROR", u"Tag not found or no config returned.")
            return False, False, False

        tag_config = dict(config[0])
        alarms = [dict(alarm) for alarm in tag_config.get("alarms", [])]
        matches = [alarm for alarm in alarms if alarm.get("name", "") == alarm_name]
        if len(matches) != 1:
            set_result("ERROR", u"Expected one configured alarm '{}'; found {}.".format(alarm_name, len(matches)))
            return False, False, False

        alarm = matches[0]
        priority_changed = "priority" in alarm
        label_changed = "label" in alarm
        decision["previousPriority"] = alarm.get("priority", u"")
        decision["previousLabel"] = alarm.get("label", u"")
        if not priority_changed and not label_changed:
            set_result("UNCHANGED", u"No priority or label overrides in configuration.")
            return True, False, False

        alarm.pop("priority", None)
        alarm.pop("label", None)
        tag_config["alarms"] = alarms
        if dry_run:
            set_result("DRY RUN", u"Would remove priority/label overrides, preserving other alarm properties.")
            return True, priority_changed, label_changed

        # Merge mode would leave omitted overrides in place.
        parent = tag_path.rsplit("/", 1)[0]
        qualities = system.tag.configure(parent, [tag_config], "o")
        if not qualities or len(qualities) != 1 or not qualities[0].isGood():
            set_result("ERROR", u"Configuration write failed: {}".format(qualities))
            return False, False, False

        updated = system.tag.getConfiguration(tag_path, False)
        updated_alarms = updated[0].get("alarms", []) if updated else []
        updated_matches = [item for item in updated_alarms if item.get("name", "") == alarm_name]
        if len(updated_matches) != 1:
            set_result("ERROR", u"Write completed, but alarm entry was not preserved on readback.")
            return False, False, False
        if "priority" in updated_matches[0] or "label" in updated_matches[0]:
            set_result("ERROR", u"Write completed, but priority/label remain in configuration on readback.")
            return False, False, False
        if dict(updated_matches[0]) != alarm:
            set_result("ERROR", u"Write completed, but other alarm properties differ on readback.")
            return False, False, False

        set_result("OK", u"Priority/label overrides removed; alarm entry and other properties preserved.")
        return True, priority_changed, label_changed

    except Exception as e:
        set_result("ERROR", unicode(e))
        return False, False, False


def csv_escape(value):
    val = u"" if value is None else unicode(value)
    if u',' in val or u'"' in val or u'\n' in val or u'\r' in val:
        val = u'"' + val.replace(u'"', u'""') + u'"'
    return val


def write_results(output_path, all_rows):
    fieldnames = ["path", "alarmName", "previousPriority", "previousLabel", "status", "message", "priorityChanged", "labelChanged"]
    lines = [u",".join(fieldnames)]
    for row in all_rows:
        lines.append(u",".join([csv_escape(row.get(col, u"")) for col in fieldnames]))
    csv_text = u"\n".join(lines) + u"\n"
    utf8      = Charset.forName("UTF-8")
    out_bytes = JString(csv_text).getBytes(utf8)
    system.file.writeFile(output_path, out_bytes)
    print(u"\n[OUTPUT] Results written to: {}".format(output_path))


def main():
    print("=" * 60)
    print("Alarm Priority/Label Override Removal - {}".format("DRY RUN MODE" if DRY_RUN else "LIVE MODE"))
    print("=" * 60)

    startTime = system.date.now().getTime()
    csv_path = choose_file()
    if csv_path is None:
        print("\nNo file chosen. Exiting.")
        return
    decisions, skipped = read_decisions(PROVIDER, csv_path)
    total = len(decisions)
    print(u"\nLoaded {} valid decision(s) from: {}\n".format(total, csv_path))
    decisionTime = system.date.now().getTime()

    if not decisions and not skipped:
        print("No rows found. Exiting.")
        return
    success = 0
    failed  = 0
    priority_changed_count = 0
    label_changed_count = 0
    for current, decision in enumerate(decisions, start=1):
        decision_success, priority_changed, label_changed = apply_decision(decision, current, total, DRY_RUN, PROVIDER)
        decision["priorityChanged"] = priority_changed
        decision["labelChanged"] = label_changed
        if priority_changed:
            priority_changed_count += 1
        if label_changed:
            label_changed_count += 1
        if decision_success:
            success += 1
        else:
            failed += 1
    write_results(build_output_path(csv_path), decisions + skipped)
    endTime = system.date.now().getTime()

    print("\n" + "=" * 12 + " Complete " + "=" * 38)
    print("Success:              {}".format(success))
    print("Failed/Skipped:       {}".format(failed + len(skipped)))
    print("=" * 60)
    print("Priority Overrides{}: {}".format(" Planned" if DRY_RUN else " Removed", priority_changed_count))
    print("Label Overrides{}:    {}".format(" Planned" if DRY_RUN else " Removed", label_changed_count))
    print("=" * 60)
    print("Decision Load Time:   {} s".format((decisionTime - startTime)/1000))
    print("Apply Time:           {} s".format((endTime - decisionTime)/1000))
    print("Total Time:           {} s".format((endTime - startTime)/1000))
    print("=" * 60)

    if (failed + len(skipped)) > 0:
        print("Errors occured during run. Review output csv for details.")

    if DRY_RUN:
        print("\n*** DRY_RUN = True. Set DRY_RUN = False to apply changes. ***")

PROVIDER = "default"
DRY_RUN = True
main()