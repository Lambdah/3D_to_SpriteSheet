bl_info = {
    "name": "3D to Sprite Sheet",
    "author": "Lambdah",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "Node Editor > Sidebar > SpriteSheet",
    "description": "Creates a compositor node setup to generate sprite sheets from image sequences.",
    "doc_url": "https://github.com/Lambdah/3D_to_SpriteSheet",
    "category": "Compositing",
}


import bpy
import os


def output_directory_string(directory):
    """ Filepath has to be a directory"""
    filepath = directory.replace("\\", "/")
    if not filepath.endswith("/"):
        filepath = filepath[:filepath.rfind("/")+1]
    return filepath
    
    
def get_img_files(directory, img_extension=".png"):
        img_files = []
        for file in os.listdir(directory):
            if file.endswith(img_extension):
                img_files.append({"name":file})
            img_files.sort(key=lambda x: x["name"])
        return img_files


def create_blank_image(width, height , name="SpriteSheet", color=(0.0, 0.0, 0.0, 0.0)):
    image = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=False)
    pixel_data = list(color) * (width * height)
    image.pixels = pixel_data
    return image


def create_sequence_node(node, image_name, offset, frames):
    sequence = node.new('CompositorNodeImage')
    sequence.image = bpy.data.images[image_name]
    sequence.image.source = 'SEQUENCE'
    sequence.frame_start=0
    sequence.frame_duration=frames
    sequence.frame_offset = offset
    return sequence


def sprite_position(index, columns, rows, sprite_width, sprite_height):
    """ Image coordinates in the sprite sheet"""
    img_width = sprite_width * columns
    img_height = sprite_height * rows
    x = (index % columns) * sprite_width - (img_width * 0.5)
    y = (index // columns) * sprite_height - (img_height * 0.5)
    return (sprite_width * 0.5 + x, -1*(sprite_height * 0.5 + y))


def create_transform_node(nodes):
    transform_node = nodes.new(type='CompositorNodeTransform')
    transform_node.location = (150, 200)
    return transform_node


def create_alpha_over(node):
    alpha_over = node.new(type='CompositorNodeAlphaOver')
    alpha_over.inputs[0].default_value = 1.0
    return alpha_over


def create_node_groups(context, group_name, columns, rows, index, image_name, frames):
    group_node = bpy.data.node_groups.new(group_name + f"{index}", 'CompositorNodeTree')
    # Create input 
    previous_sprite = group_node.interface.new_socket(
        name="previous_sprite",
        description="previous sprites from last groups",
        in_out="INPUT"
    )
    group_input = group_node.nodes.new(type='NodeGroupInput')

    # Create output
    current_sprite = group_node.interface.new_socket(
        name="current_sprite",
        description="current sprite output",
        in_out="OUTPUT"
    )
    group_output = group_node.nodes.new(type='NodeGroupOutput')
    group_output.location = (200, 0)

    # Create node groups
    sequence_node = create_sequence_node(group_node.nodes, image_name, index, frames)
    sequence_node.location = (-300, -300)

    transform_node = create_transform_node(group_node.nodes)
    transform_node.inputs["X"].default_value, transform_node.inputs["Y"].default_value = sprite_position(index, columns, rows, *bpy.data.images[image_name].size)
    transform_node.location = (-100, -300)

    alpha_over = create_alpha_over(group_node.nodes)
    alpha_over.location = (100, 0)

    # Create links
    group_node.links.new(sequence_node.outputs['Image'], transform_node.inputs[0])
    group_node.links.new(group_input.outputs['previous_sprite'], alpha_over.inputs[1])
    group_node.links.new(transform_node.outputs['Image'], alpha_over.inputs[2])
    group_node.links.new(alpha_over.outputs['Image'], group_output.inputs['current_sprite'])
    return group_node


def create_compositor(operator, context, group_name, columns, rows):
    try:
        bpy.context.scene.use_nodes = True
        _directory = context.scene.spritesheet_variables.file_directory
        _directory = output_directory_string(_directory)
        img_files = get_img_files(_directory)
        frame_duration = len(img_files)
        bpy.ops.image.open(directory=_directory, files=img_files)
    except RuntimeError:
        context.scene.spritesheet_errors.error = 'No usable images files in the current directory'
        return None
    img_file = bpy.data.images[img_files[0]["name"]]
    # Create blank sprite image
    sprite_node = context.scene.node_tree.nodes.new('CompositorNodeImage')
    sprite_node.location = (-600, 150)
    img_width, img_height = img_file.size
    if((columns * rows) < frame_duration):
        context.scene.spritesheet_errors.warning = 'Sprite sheet is too small. Increase rows or columns.'
    if (img_width == 0 and img_height == 0):
        img = bpy.data.images.load(_directory + img_files[0]["name"])
        img_width, img_height = img.size
    # Adjust the render resolution to fit the sprite sheet
    bpy.context.scene.render.resolution_x = img_width * columns
    bpy.context.scene.render.resolution_y = img_height * rows
    bpy.context.scene.render.film_transparent = True
    # Create the blank background sprite sheet
    sprite_node.image = create_blank_image(img_width * columns, img_height * rows)
    prev_sprite_node = sprite_node
    
    for i in range(0, frame_duration):
        node_group = create_node_groups(context, group_name, columns, rows, i, img_file.name, frame_duration)
        comp_node = context.scene.node_tree.nodes.new('CompositorNodeGroup')
        comp_node.node_tree = bpy.data.node_groups[node_group.name]
        comp_node.location = 0, -100*i
        context.scene.node_tree.links.new(prev_sprite_node.outputs[0], comp_node.inputs[0])
        prev_sprite_node = comp_node
    
    return comp_node


def get_scene_node(node_str):
    scene = bpy.context.scene
    return next((node for node in scene.node_tree.nodes if node.type == node_str), None)


class NODE_OT_open_file_sequence(bpy.types.Operator):
    """Opens a file browser to select an image sequence"""
    bl_idname="wm.open_file_sequence"
    bl_label="Open Image Sequence"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")


    def get_img_files(self, img_extension=".png"):
        img_files = []
        self.directory = self.directory.replace("\\", "\\\\")
        for file in os.listdir(self.directory):
            if file.endswith(img_extension):
                img_files.append({"name":file})
            img_files.sort(key=lambda x: x["name"])
        return img_files
    
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    
    def execute(self, context):
        scene = context.scene
        scene.use_nodes = True
        context.scene.spritesheet_variables.file_directory = self.filepath
        bpy.ops.node.spritesheet_operator()
        
        if (context.scene.spritesheet_errors.warning):
            self.report({'WARNING'},context.scene.spritesheet_errors.warning)
            context.scene.spritesheet_errors.warning = ""
        if (context.scene.spritesheet_errors.error):
            self.report({'ERROR'}, context.scene.spritesheet_errors.error)
            context.scene.spritesheet_errors.error = ""
        return {'FINISHED'}
    

# Operator
class NODE_OT_spritesheetcompositor(bpy.types.Operator):
    """Creates node groups in the compositor to build a sprite sheet"""
    bl_idname = "node.spritesheet_operator"
    bl_label = "Add Group Severals images together into a single sprite sheet"


    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space.type == 'NODE_EDITOR'

    def execute(self, context):
        columns = context.scene.spritesheet_variables.columns
        rows = context.scene.spritesheet_variables.rows
        
        # Create the group
        custom_node_name = "sprite"
        comp_node = create_compositor(self, context, custom_node_name, columns, rows)
        if (comp_node is None):
            return {'CANCELLED'}
        
        viewer_node = get_scene_node('VIEWER')
        composite_node = get_scene_node('COMPOSITE')

        if not viewer_node:
            viewer_node = context.scene.node_tree.nodes.new('CompositorNodeViewer')
            viewer_node.location = (200, 300)

        if not composite_node:
            composite_node = context.scene.node_tree.nodes.new('CompositorNodeComposite')
            composite_node.location = (400, 300)
        
        if viewer_node and composite_node:
            bpy.context.scene.node_tree.links.new(comp_node.outputs[0], viewer_node.inputs[0])
            bpy.context.scene.node_tree.links.new(comp_node.outputs[0], composite_node.inputs[0])
        
        return {'FINISHED'}
        
    

# Panel
class NODE_PT_spritesheetPanel(bpy.types.Panel):
    bl_idname = "NODE_PT_spritesheetPanel"
    bl_space_type = 'NODE_EDITOR'
    bl_label = "Create a sprite sheet"
    bl_region_type = "UI"
    bl_category = "SpriteSheet"


    @classmethod
    def poll(self,context):
        return context.object is not None


    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Columns and Rows")
        row = layout.row()
        row.prop(context.scene.spritesheet_variables, "columns")
        row.prop(context.scene.spritesheet_variables, "rows")
        row = layout.row()
        layout.operator(NODE_OT_open_file_sequence.bl_idname)
        layout.separator()
        row = layout.row()
        

class NODE_pointers(bpy.types.PropertyGroup):
    rows : bpy.props.IntProperty(
            name="Rows",
            description="Number of vertical rows in the sprite sheet",
            default=1,
            min=1
            )
    columns : bpy.props.IntProperty(
            name="Columns",
            description="Number of horizontal columns in the sprite sheet",
            default=1,
            min=1
            )
    file_directory: bpy.props.StringProperty(
        name="Directory",
        description="Directory to load image sequence from",
        default="",
        subtype='DIR_PATH'
        )


class NODE_errors(bpy.types.PropertyGroup):
    error: bpy.props.StringProperty(
        name="Error",
        description="Error message",
        default=""
        )
    warning: bpy.props.StringProperty(
        name="Warning",
        description="Warning message",
        default=""
        )
    


# Register
def register():
    bpy.utils.register_class(NODE_pointers)
    bpy.utils.register_class(NODE_errors)
    bpy.types.Scene.spritesheet_variables = bpy.props.PointerProperty(type=NODE_pointers)
    bpy.types.Scene.spritesheet_errors = bpy.props.PointerProperty(type=NODE_errors)
    bpy.utils.register_class(NODE_OT_spritesheetcompositor)
    bpy.utils.register_class(NODE_PT_spritesheetPanel)
    bpy.utils.register_class(NODE_OT_open_file_sequence)
   


def unregister():
    bpy.utils.unregister_class(NODE_pointers)
    bpy.utils.unregister_class(NODE_errors)
    del bpy.types.Scene.spritesheet_variables
    del bpy.types.Scene.spritesheet_errors
    bpy.utils.unregister_class(NODE_OT_spritesheetcompositor)
    bpy.utils.unregister_class(NODE_PT_spritesheetPanel)
    bpy.utils.unregister_class(NODE_OT_open_file_sequence)
    
    

if __name__ == "__main__":
    register()