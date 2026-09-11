# Version history:
# V1 - Applies keep, delete, and priority-change actions from a CSV file.
# V2 - Adds priority/label reporting, medium-priority validation, and custom-email cleanup.
# V3 - Adds optional alarm-label updates and summary counters for changed fields.
# V4 - Adds optional alarm-name updates through the CSV newName column.

import system
from java.lang import String as JString
from java.nio.charset import Charset

VALID_PRIORITIES = {"Diagnostic", "Low", "High", "Critical"}
VALID_ACTIONS    = {"keep", "delete", "change priority"}

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


def checkIfChildUDT(provider, tagPath):
    segments = tagPath.strip('/').split('/')
    
    for i in range(len(segments) - 1):
        currentPath = "["+provider+"]_types_/" + "/".join(segments[:i+1])
        
        config = system.tag.getConfiguration(currentPath, False)
        
        if config and len(config) > 0:
            tagType = config[0].get('tagType', '')
            
            # UDT instances report tagType as "UdtInstance"
            if str(tagType) == 'UdtInstance':
                return True
    
    return False


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
    idx_action = col("action")
    idx_pri    = col("newpriority")
    idx_label  = col("newLabel")
    idx_new_name = col("newName")
    missing_headers = []
    if idx_path   is None: missing_headers.append("path")
    if idx_name   is None: missing_headers.append("alarmName")
    if idx_action is None: missing_headers.append("action")
    if missing_headers:
        print("  [ERROR] CSV is missing required header column(s): {}".format(", ".join(missing_headers)))
        return [], []
    decisions = []
    skipped   = []
    configTags = []

    def get(row, idx):
        if idx is None or idx >= len(row):
            return u""
        return row[idx].strip()

    for i, row in enumerate(rows[1:], start=2):
        path_   = get(row, idx_path)
        name    = get(row, idx_name)
        action  = get(row, idx_action).lower()
        new_pri = get(row, idx_pri) if idx_pri is not None else u""
        new_label = get(row, idx_label) if idx_label is not None else u""
        new_name = get(row, idx_new_name) if idx_new_name is not None else u""
        errors = []
        record = {
            "path":        path_,
            "alarmName":   name,
            "action":      action,
            "newPriority": new_pri,
            "newLabel":    new_label,
            "newName":     new_name,
            "status":      u"",
            "message":     u"",
            "customEmailChanged": False,
            "labelChanged": False,
            "nameChanged": False,
        }

        if "/Config/" in path_ and not "_Base" in path_:
            error_msg = u"Skipping Config Child Tag"
            print(u"  [SKIP] Row {}: {} | Errors: {}".format(i, path_, error_msg))
            record["status"]  = u"CONFIG TAG"
            record["message"] = error_msg
            configTags.append(record)
            continue
        elif checkIfChildUDT(provider, path_):
            error_msg = u"Skipping Tag in Child UDT"
            print(u"  [SKIP] Row {}: {} | Errors: {}".format(i, path_, error_msg))
            record["status"]  = u"CHILD INSTANCE TAG"
            record["message"] = error_msg
            configTags.append(record)
            continue

        if not path_:
            errors.append("Missing Path")
        if not name:
            errors.append("Missing AlarmName")
        if action not in VALID_ACTIONS:
            errors.append("Invalid Action: '{}'".format(action))
        if action == "change priority":
            if not new_pri:
                errors.append("Missing NewPriority")
            elif new_pri not in VALID_PRIORITIES:
                errors.append("Invalid NewPriority: '{}'".format(new_pri))

        if errors:
            error_msg = u", ".join(errors)
            print(u"  [SKIP] Row {}: {} | Errors: {}".format(i, path_, error_msg))
            record["status"]  = u"SKIPPED"
            record["message"] = error_msg
            skipped.append(record)
            continue

        decisions.append(record)
    return decisions, skipped, configTags


def apply_decision(decision, current, total, dry_run, provider):
    success = False
    customEmailRemoved = False
    labelChanged = False
    nameChanged = False
    tag_path   = "[" + provider + "]_types_/" + decision["path"]
    alarm_name = decision["alarmName"]
    action     = decision["action"]
    new_pri    = decision["newPriority"]
    new_label  = decision["newLabel"]
    new_name   = decision["newName"]
    print(u"\n[{}/{}] [{}] {}  |  Alarm: '{}'  |  Action: {}  ->  {} | Label: '{}' | New Name: '{}'".format(
        current,
        total,
        "DRY RUN" if dry_run else "APPLY",
        tag_path,
        alarm_name,
        action,
        new_pri if new_pri else u"",
        new_label if new_label else u"",
        new_name if new_name else u""
    ))
    def set_result(status, message, previousPriority="", currentLabel=""):
        decision["status"]  = status
        decision["message"] = message
        decision["previousPriority"] = previousPriority
        decision["currentLabel"] = currentLabel
    try:
        sts = ""
        msg = ""
        config = system.tag.getConfiguration(tag_path, False)
        if not config:
            sts += "ERROR"
            msg += u"Tag not found or no config returned."
            print(u"  [{}] {}".format(sts, msg))
            set_result(sts, msg)
        else:
            tag_config = config[0]
            alarms     = tag_config.get("alarms", [])
            match_idx = None

            for i, alarm in enumerate(alarms):
                if alarm.get("name", "").strip() == alarm_name:
                    match_idx = i
                    break

            if match_idx is None:
                sts += "ERROR"
                msg += u"Alarm '{}' not found on tag.".format(alarm_name)
                print(u"  [{}] {}".format(sts, msg))
                set_result(sts, msg)
            else:
                try:
                    currentlabel = alarms[match_idx]["label"]["value"]
                except:
                    sts += "WARN "
                    msg += u"LABEL WITHOUT BINDING."
                    try:
                        currentlabel = alarms[match_idx]["label"]
                    except:
                        currentlabel = ""
                        msg += u"LABEL IS MISSING."

                previousPriority = alarms[match_idx].get("priority", "Low")

                if action == "delete":
                    if not dry_run:
                        alarms.pop(match_idx)
                        tag_config["alarms"] = alarms
                        parent = tag_path.rsplit("/", 1)[0] if "/" in tag_path else "[default]"
                        system.tag.configure(parent, [tag_config], "o")
                    sts += "OK" if not dry_run else "DRY RUN"
                    msg += u"Alarm deleted{}.".format(u" (dry run)" if dry_run else u"")
                    print(u"  [{}] {}".format(sts, msg))
                    set_result(sts, msg, previousPriority, currentlabel)
                    success = True

                elif action in ("keep", "change priority"):
                    if action == "change priority":
                        alarms[match_idx]["priority"] = new_pri

                    if new_name and new_name != alarm_name:
                        alarms[match_idx]["name"] = new_name
                        nameChanged = True

                    if "CustomEmailSubject" in alarms[match_idx] or "CustomEmailMessage" in alarms[match_idx]:
                        alarms[match_idx]["CustomEmailSubject"] = None
                        alarms[match_idx]["CustomEmailMessage"] = None
                        customEmailRemoved = True

                    if str(new_label) not in ("", "0", 0):
                        alarms[match_idx]["label"] = {'bindType': 'Expression', 'value': new_label}
                        labelChanged = True

                    if action == "keep" and str(previousPriority).lower() == "medium":
                        sts += "ERROR"
                        msg += u"Alarm with Medium priority set to keep."
                        print(u"  [{}] {}".format(sts, msg))
                        set_result(sts, msg, previousPriority, currentlabel)
                        success = False
                    else:
                        if not dry_run:
                            tag_config["alarms"] = alarms
                            parent = tag_path.rsplit("/", 1)[0] if "/" in tag_path else "[default]"
                            system.tag.configure(parent, [tag_config], "o")

                        msg += u"Priority set to '{}'{}.".format(new_pri, u" (dry run)" if dry_run else u"") if action == "change priority" else \
                         u"No change to Priority made{}.".format(u" (dry run)" if dry_run else u"")

                        if customEmailRemoved:
                            msg += u" Custom email fields will be removed." if dry_run else u" Custom email fields are removed."
                        if labelChanged:
                            msg += u" Label will be updated." if dry_run else u" Label updated."
                        if nameChanged:
                            msg += u" Name will be updated to '{}'.".format(new_name) if dry_run else u" Name updated to '{}'.".format(new_name)

                        sts += "OK" if not dry_run else "DRY RUN"
                        print(u"  [{}] {}".format(sts, msg))
                        set_result(sts, msg, previousPriority, currentlabel)
                        success = True

                else:
                    sts += "ERROR"
                    msg += u"Unrecognised action: '{}'.".format(action)
                    print(u"  [{}] {}".format(sts, msg))
                    set_result(sts, msg, previousPriority, currentlabel)
                    success = False

    except Exception as e:
        sts += "ERROR"
        msg += unicode(e)
        print(u"  [{}] {}".format(sts, msg))
        set_result(sts, msg)
        success = False

    return success, customEmailRemoved, labelChanged, nameChanged


def csv_escape(value):
    val = u"" if value is None else unicode(value)
    if u',' in val or u'"' in val or u'\n' in val or u'\r' in val:
        val = u'"' + val.replace(u'"', u'""') + u'"'
    return val


def write_results(output_path, all_rows):
    fieldnames = ["path", "alarmName", "newName", "previousPriority", "action", "newPriority", "status", "message", "customEmailChanged", "labelChanged", "nameChanged", "currentLabel", "newLabel"]
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
    print("Alarm Modifier - {}".format("DRY RUN MODE" if DRY_RUN else "LIVE MODE"))
    print("=" * 60)

    startTime = system.date.now().getTime()
    csv_path = choose_file()
    if csv_path is None:
        print("\nNo file chosen. Exiting.")
        return
    decisions, skipped, configTags = read_decisions(PROVIDER, csv_path)
    total = len(decisions)
    print(u"\nLoaded {} valid decision(s) from: {}\n".format(total, csv_path))
    decisionTime = system.date.now().getTime()

    if not decisions and not skipped and not configTags:
        print("No rows found. Exiting.")
        return
    success = 0
    failed  = 0
    custom_email_changed_count = 0
    label_changed_count = 0
    name_changed_count = 0
    for current, decision in enumerate(decisions, start=1):
        decision_success, custom_email_changed, label_changed, name_changed = apply_decision(decision, current, total, DRY_RUN, PROVIDER)
        decision["customEmailChanged"] = custom_email_changed
        decision["labelChanged"] = label_changed
        decision["nameChanged"] = name_changed
        if custom_email_changed:
            custom_email_changed_count += 1
        if label_changed:
            label_changed_count += 1
        if name_changed:
            name_changed_count += 1
        if decision_success:
            success += 1
        else:
            failed += 1
    write_results(build_output_path(csv_path), decisions + skipped + configTags)
    endTime = system.date.now().getTime()

    print("\n" + "=" * 12 + " Complete " + "=" * 38)
    print("Success:              {}".format(success))
    print("Failed/Skipped:       {}".format(failed + len(skipped)))
    print("Skipped Config Tags:  {}".format(len(configTags)))
    print("=" * 60)
    print("Custom Email Removed: {}".format(custom_email_changed_count))
    print("Label Changed:        {}".format(label_changed_count))
    print("Name Changed:         {}".format(name_changed_count))
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