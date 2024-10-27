import os
import numpy as np
from PIL import Image
from io import BytesIO
import subprocess  # Import subprocess for video processing
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.togglebutton import ToggleButton
from kivy.clock import Clock
from kivy.uix.anchorlayout import AnchorLayout
import platform
import ffmpeg

# Compression Functions
def calculate_mse(image1, image2):
    arr1 = np.array(image1)
    arr2 = np.array(image2)
    mse = np.mean((arr1 - arr2) ** 2)
    return mse

def calculate_psnr(mse, max_pixel=255.0):
    if mse == 0:
        return float('inf')  # No difference between images
    return 10 * np.log10((max_pixel ** 2) / mse)

# Compression Screen
class CompressionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build()
        self.is_processing = False  # To track if processing is ongoing
        self.current_file_index = 0  # Index to track current file being processed
        self.total_original_size = 0  # Initialize total original size
        self.total_compressed_size = 0  # Initialize total compressed size

    def build(self):
        # Main layout with AnchorLayout to position widgets at the top
        root_layout = AnchorLayout(anchor_y='top')

        # BoxLayout to hold all the content in vertical orientation
        main_layout = BoxLayout(orientation='vertical', size_hint=(1, None))

        # Input Directory Section
        input_layout = BoxLayout(orientation='vertical', size_hint=(1, None), height=40)
        self.input_label = Label(text='Select Input Directory:', size_hint_y=None, height=40)
        self.filechooser = FileChooserListView(path=os.getcwd(), size_hint=(1, None), height=300)
        self.filechooser.bind(path=self.update_selected_path)

        input_layout.add_widget(self.input_label)
        main_layout.add_widget(input_layout)
        main_layout.add_widget(self.filechooser)

        # Output Directory Section
        output_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40)
        self.output_label = Label(text='Output Directory:', size_hint_y=None, height=40)
        user_home = os.getcwd()
        self.output_dir_input = TextInput(text=os.path.join(user_home, 'compressed_images'), multiline=False, size_hint_y=None, height=40)

        input_path_layout = BoxLayout(orientation='horizontal', size_hint=(1, None), height=40)
        self.selected_path_label = Label(text='Selected Path:', size_hint_y=None, height=40)
        self.selected_path_input = TextInput(text=self.filechooser.path, multiline=False, size_hint_y=None, height=40)

        input_path_layout.add_widget(self.selected_path_label)
        input_path_layout.add_widget(self.selected_path_input)

        output_layout.add_widget(self.output_label)
        output_layout.add_widget(self.output_dir_input)

        self.path_box = BoxLayout(orientation='vertical', size_hint=(1, None), height=80)
        self.path_box.add_widget(input_path_layout)
        self.path_box.add_widget(output_layout)

        main_layout.add_widget(self.path_box)

        # Toggle buttons for selecting compression type
        self.compress_type_toggle = BoxLayout(orientation='horizontal', size_hint=(1, None), height=50)
        self.image_toggle = ToggleButton(text='Compress Images', group='compress_type', state='down')
        self.video_toggle = ToggleButton(text='Compress Videos', group='compress_type', state='normal')
        self.compress_type_toggle.add_widget(self.image_toggle)
        self.compress_type_toggle.add_widget(self.video_toggle)
        main_layout.add_widget(self.compress_type_toggle)

        # Button Section
        self.process_button = Button(text='Start Compression', size_hint_y=None, height=50, on_press=self.start_compression)
        main_layout.add_widget(self.process_button)

        # Settings Button
        settings_button = Button(text='Settings', size_hint_y=None, height=50, on_press=self.go_to_settings)
        main_layout.add_widget(settings_button)

        # Scrollable Result Section
        self.result_scroll = ScrollView(size_hint=(1, None), size=(400, 200))
        self.result_text_input = TextInput(size_hint_y=None, multiline=True, readonly=True)
        self.result_text_input.bind(minimum_height=self.result_text_input.setter('height'))

        self.result_scroll.add_widget(self.result_text_input)
        main_layout.add_widget(self.result_scroll)

        # Setting the size_hint_y for dynamic resizing
        main_layout.bind(minimum_height=main_layout.setter('height'))
        main_layout.size_hint_y = None

        # Add main layout to root layout (AnchorLayout)
        root_layout.add_widget(main_layout)
        
        # Add root layout to the screen
        self.add_widget(root_layout)

    def go_to_settings(self, instance):
        # Switch to Settings screen
        self.manager.current = 'settings'

    def update_selected_path(self, instance, value):
        """Update the selected path input when the file chooser path changes."""
        self.selected_path_input.text = value  # Update the text input to reflect the current path

    def start_compression(self, instance):
        if not self.is_processing:  # Check if already processing
            self.is_processing = True  # Set the flag to indicate processing has started
            self.process_button.disabled = True  # Disable the button to prevent multiple clicks
            self.current_file_index = 0  # Reset the file index
            self.total_original_size = 0  # Reset total original size
            self.total_compressed_size = 0  # Reset total compressed size
            
            # Start the processing in a new thread
            Clock.schedule_once(self.process_next_file, 0)  # Schedule the next file processing
    def change_output(self, result):
        self.result_text_input.text = result
    def process_next_file(self, dt):
        # Get the selected path from the FileChooser
        input_directory = self.selected_path_input.text
        output_directory = self.output_dir_input.text

        if input_directory:
            if os.path.isdir(input_directory):
                if self.image_toggle.state == 'down':
                    # Process images
                    files = [f for f in os.listdir(input_directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                else:
                    # Process videos
                    files = [f for f in os.listdir(input_directory) if f.lower().endswith(('.mp4', '.avi', '.mov', ".wmv"))]
                
                if self.current_file_index < len(files):
                    filename = files[self.current_file_index]
                    input_file_path = os.path.join(input_directory, filename)

                    if self.image_toggle.state == 'down':
                        # Process the image
                        self.compress_image(input_file_path, filename, output_directory)
                    else:
                        # Process the video
                        self.compress_video(input_file_path, filename, output_directory)
                    
                    self.current_file_index += 1  # Move to the next file
                    Clock.schedule_once(self.process_next_file, 0)  # Schedule the next file processing
                else:
                    self.finalize_results()  # Finalize results after processing all files
            else:
                self.result_text_input.text = 'Please select a valid input directory.'
        else:
            self.result_text_input.text = 'Please select a valid input directory.'

    def compress_image(self, input_image_path, filename, output_directory):
        original_size = os.path.getsize(input_image_path)
        self.total_original_size += original_size  # Accumulate original size

        with Image.open(input_image_path) as original:
            original = original.convert('RGB')

            best_image = None
            best_image_details = None
            qualities = [85, 70, 50, 30]  # Quality levels

            for quality in qualities:
                with BytesIO() as img_byte_arr:
                    original.save(img_byte_arr, format='JPEG', quality=quality)
                    img_byte_arr.seek(0)

                    with Image.open(img_byte_arr) as compressed:
                        compressed = compressed.convert('RGB')
                        compressed_size = img_byte_arr.tell()

                        mse = calculate_mse(original, compressed)
                        psnr = calculate_psnr(mse)

                        if psnr >= 30 and mse <= 50:
                            best_image = img_byte_arr.getvalue()
                            best_image_details = (quality, mse, psnr, compressed_size)
                        else:
                            break

            if best_image:
                app = App.get_running_app()
                if app.settings['overwrite_files']:
                    output_image_path = input_image_path  # Overwrite the original file
                else:
                    output_image_path = os.path.join(output_directory, f'compressed_q{best_image_details[0]}_{filename}')
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(output_image_path), exist_ok=True)

                with open(output_image_path, 'wb') as f:
                    f.write(best_image)

                self.total_compressed_size += best_image_details[3]  # Accumulate compressed size
                
                # Prepare the result text
                result_text = f'Saved: {output_image_path}, Quality: {best_image_details[0]}, ' \
                              f'MSE: {best_image_details[1]:.2f}, PSNR: {best_image_details[2]:.2f}, ' \
                              f'Original Size: {original_size / 1024:.2f} KB, Compressed Size: {best_image_details[3] / 1024:.2f} KB'
                # Schedule the result text update
                Clock.schedule_once(lambda dt: self.change_output(result_text), 0)
            else:
                self.change_output(f'Could not compress {filename} within acceptable limits.\n')


    def compress_video(self, input_video_path, filename, output_directory, crf_value="30"):
        original_size = os.path.getsize(input_video_path)
        self.total_original_size += original_size  # Accumulate original size

        # Ensure the output directory exists
        os.makedirs(output_directory, exist_ok=True)
        
        # Output file path (always MP4)
        output_video_path = os.path.join(output_directory, f'compressed_{filename}.mp4')
        """
        # Get the original frame rate (use ffprobe to retrieve it)
        original_frame_rate = subprocess.check_output(
            f'ffprobe -v 0 -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "{input_video_path}"',
            shell=True
        ).decode().strip()
        """
        try:
            # Use ffmpeg-python to compress the video
            (
                ffmpeg
                .input(input_video_path, r=15)  # Set input frame rate
                .output(output_video_path, vcodec='libx264', crf=crf_value, 
                         acodec='aac', b='128k', pix_fmt='yuv420p')
                .run(overwrite_output=True)  # Overwrite the output file if it exists
            )

            # Check the size of the compressed file
            compressed_size = os.path.getsize(output_video_path)
            self.total_compressed_size += compressed_size  # Accumulate compressed size

            # Generate result text
            result_text = (f'Saved: {output_video_path}, Original Size: {original_size / 1024:.2f} KB, '
                           f'Compressed Size: {compressed_size / 1024:.2f} KB\n')
            # Output result
            Clock.schedule_once(lambda dt: self.change_output(result_text), 0)
        except ffmpeg.Error as e:
            self.change_output(f'Failed to compress {filename}. Error: {e.stderr.decode()}\n')

    def finalize_results(self):
        # Enable the button after processing
        self.process_button.disabled = False
        self.is_processing = False  # Reset processing flag
        total_text = f'Total Original Size: {self.total_original_size}, Total Compressed Size: {self.total_compressed_size}\nCompression Ratio: {self.total_original_size/self.total_compressed_size}'
        self.result_text_input.text += total_text

# Settings Screen
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build()

    def build(self):
        layout = BoxLayout(orientation='vertical')

        # Overwrite Files Checkbox
        self.overwrite_checkbox = ToggleButton(text='Overwrite Original Files', group='overwrite', state='normal')
        layout.add_widget(self.overwrite_checkbox)

        # Settings layout and back button
        back_button = Button(text='Back to Compression', on_press=self.go_back)
        layout.add_widget(back_button)
        self.add_widget(layout)

    def go_back(self, instance):
        # Switch back to Compression screen
        self.manager.current = 'compression'

# Main Application
class MyApp(App):
    def build(self):
        self.title = 'Image and Video Compression App'
        sm = ScreenManager()
        sm.add_widget(CompressionScreen(name='compression'))
        sm.add_widget(SettingsScreen(name='settings'))
        self.settings = {'overwrite_files': False}  # Settings storage
        return sm

if __name__ == '__main__':
    MyApp().run()
