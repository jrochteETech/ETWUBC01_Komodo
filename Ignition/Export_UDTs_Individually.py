from java.io import File
from javax.swing import JFileChooser


ROOT_UDT_PATH = "[default]_types_"


def browse_and_export_udts(base_path, output_folder):
    if not output_folder.exists() and not output_folder.mkdirs():
        raise Exception(
            "Could not create folder: %s" %
            output_folder.getAbsolutePath()
        )

    total_exported = 0
    total_failed = 0
    browse_results = system.tag.browse(base_path, {})

    for item in browse_results.getResults():
        tag_type = item["tagType"].toString()
        full_path = str(item["fullPath"])
        name = str(item["name"])

        if tag_type == "UdtType":
            try:
                exported_json = system.tag.exportTags(
                    tagPaths=[full_path],
                    recursive=True,
                    exportType="json"
                )
                output_file = File(output_folder, name + ".json")
                system.file.writeFile(
                    output_file.getAbsolutePath(),
                    exported_json
                )

                total_exported += 1
                print("Exported: %s" % output_file.getAbsolutePath())

            except Exception as error:
                total_failed += 1
                print("FAILED: %s" % full_path)
                print("        %s" % error)

        elif tag_type == "Folder":
            subfolder = File(output_folder, name)
            exported, failed = browse_and_export_udts(
                full_path,
                subfolder
            )
            total_exported += exported
            total_failed += failed

    return total_exported, total_failed


chooser = JFileChooser()
chooser.setDialogTitle("Select export folder for UDT definitions")
chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)

result = chooser.showSaveDialog(None)

if result != JFileChooser.APPROVE_OPTION:
    print("Export cancelled.")

else:
    selected_root = chooser.getSelectedFile()

    print("")
    print("Exporting UDT definitions...")

    total_exported, total_failed = browse_and_export_udts(
        ROOT_UDT_PATH,
        selected_root
    )

    print("")
    print("Export complete.")
    print("Total exported: %d" % total_exported)
    print("Total failed: %d" % total_failed)
    print("Destination: %s" % selected_root.getAbsolutePath())