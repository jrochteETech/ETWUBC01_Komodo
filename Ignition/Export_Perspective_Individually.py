from com.inductiveautomation.ignition.designer import IgnitionDesigner
from com.inductiveautomation.ignition.common.resourcecollection import ResourceType
from com.inductiveautomation.ignition.common.project import ProjectFileUtil
from java.io import File, FileOutputStream
from java.util import Collections
from javax.swing import JFileChooser


# Each entry is:
# (output folder name, module ID, resource type ID)
RESOURCE_GROUPS = [
    ("Views", "com.inductiveautomation.perspective", "views"),
    ("Styles", "com.inductiveautomation.perspective", "style-classes"),
    ("Scripts", "ignition", "script-python")
]


def export_resource(resource, category_root, manifest):
    resource_path = resource.getResourcePath()

    # Example: Templates/Motors/MotorFaceplate
    path_text = str(resource_path.getPath()).replace("\\", "/")
    path_parts = [part for part in path_text.split("/") if part]

    if not path_parts:
        raise Exception("Resource has no usable path: %s" % resource_path)

    resource_name = path_parts[-1]
    parent_parts = path_parts[:-1]

    output_folder = category_root

    if parent_parts:
        relative_folder = File.separator.join(parent_parts)
        output_folder = File(category_root, relative_folder)

    if not output_folder.exists() and not output_folder.mkdirs():
        raise Exception(
            "Could not create folder: %s" %
            output_folder.getAbsolutePath()
        )

    output_file = File(output_folder, resource_name + ".zip")
    output_stream = None

    try:
        output_stream = FileOutputStream(output_file)

        ProjectFileUtil.exportToZip(
            manifest,
            Collections.singletonList(resource),
            output_stream
        )

        return output_file

    except:
        # Do not leave a partial ZIP after a failed export.
        if output_file.exists():
            output_file.delete()
        raise

    finally:
        if output_stream is not None:
            try:
                output_stream.close()
            except:
                pass


designer_context = IgnitionDesigner.getFrame().getContext()
project = designer_context.getProject()
manifest = project.getManifest()

chooser = JFileChooser()
chooser.setDialogTitle(
    "Select export folder for Perspective resources and scripts"
)
chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)

result = chooser.showSaveDialog(IgnitionDesigner.getFrame())

if result != JFileChooser.APPROVE_OPTION:
    print("Export cancelled.")

else:
    selected_root = chooser.getSelectedFile()

    total_exported = 0
    total_failed = 0

    for group_name, module_id, type_id in RESOURCE_GROUPS:
        resource_type = ResourceType(module_id, type_id)
        resources = project.getResourcesOfType(resource_type)
        category_root = File(selected_root, group_name)

        group_exported = 0
        group_failed = 0

        print("")
        print("Exporting %s..." % group_name)

        for resource in resources:
            try:
                output_file = export_resource(
                    resource,
                    category_root,
                    manifest
                )

                group_exported += 1
                total_exported += 1
                print("Exported: %s" % output_file.getAbsolutePath())

            except Exception as error:
                group_failed += 1
                total_failed += 1
                print("FAILED: %s" % resource.getResourcePath())
                print("        %s" % error)

        print("%s exported: %d" % (group_name, group_exported))
        print("%s failed: %d" % (group_name, group_failed))

    print("")
    print("Export complete.")
    print("Total exported: %d" % total_exported)
    print("Total failed: %d" % total_failed)
    print("Destination: %s" % selected_root.getAbsolutePath())