from pathlib import Path
import dominate, dominate.tags as tags
import subprocess

def metric_scale_bar(size_mm:int):
	return tags.div(f'←{size_mm} mm→', style=f'width: {size_mm}mm; color: white; background-color: rgb(111,111,111); text-align: center; margin: 2px;')

class PCBReportGenerator:
	def __init__(self, path_to_KiCad_project:Path):
		self._path_to_KiCad_project = Path(path_to_KiCad_project)
		self._report = dominate.document(title = self.path_to_KiCad_project.name)
		self.KiCad_project_name # Will validate the directory.

	@property
	def path_to_KiCad_project(self):
		return self._path_to_KiCad_project

	@property
	def path_to_PCB_report(self):
		return self.path_to_KiCad_project/'PCB_report'

	@property
	def path_to_PCB_report_data(self):
		return self.path_to_PCB_report/'data'

	@property
	def KiCad_project_name(self):
		if not hasattr(self, '_KiCad_project_name'):
			name = [p.stem for p in self.path_to_KiCad_project.iterdir() if p.suffix=='.kicad_pro']
			if len(name) != 1:
				raise RuntimeError(f'Cannot find one and only one `.kicad_pro` file in {self.path_to_KiCad_project}. ')
			self._KiCad_project_name = name[0]
		else:
			return self._KiCad_project_name

	@property
	def path_to_KiCad_pcb_file(self):
		return self.path_to_KiCad_project/f'{self.KiCad_project_name}.kicad_pcb'

	def _parse_layers(self):
		layers = []
		with open(self.path_to_KiCad_pcb_file, 'r') as ifile:
			for line in ifile:
				if '(layers' not in line:
					continue
				initial_indentation_level = len(line.split('(')[0])
				while True:
					line = next(ifile)
					current_indentation_level = len(line.split('(')[0])
					if current_indentation_level <= initial_indentation_level or line == line.split('(')[0]:
						return layers
					layer_name = line.split('"')[1].lstrip('"').rstrip('"')
					layers.append(layer_name)

	def _include_SVG_layers(self):
		path_to_folder_with_SVG_files_of_the_layers = self.path_to_PCB_report_data/'layers_SVG'

		path_to_folder_with_SVG_files_of_the_layers.mkdir(parents=True)

		# Layers to be included in the report, the actual layers will be the intersection between this list and the actual layers in the PCB, e.g. `In77.Cu` will not be created if such layer is not in the actual PCB.
		LAYERS_TO_INCLUDE = [
			'F.Cu',
		] + [f'In{i}.Cu' for i in range(99)] + [
			'B.Cu',
			'B.SilkS',
			'F.SilkS',
			'B.Mask',
			'F.Mask',
			'Edge.Cuts',
			'Cmts.User',
		]

		actual_layers_in_PCB = self._parse_layers()
		for layer in [l for l in LAYERS_TO_INCLUDE if l in actual_layers_in_PCB]:
			cmd = ['kicad-cli','pcb','export','svg',str(self.path_to_KiCad_pcb_file),'--layers',layer,'--output',f'{path_to_folder_with_SVG_files_of_the_layers}/{layer}.svg','--page-size-mode','2','--exclude-drawing-sheet','--black-and-white']
			subprocess.run(cmd)

		if len(list(path_to_folder_with_SVG_files_of_the_layers.iterdir())) == 0:
			raise RuntimeError(f'Cannot find the layers in {path_to_folder_with_SVG_files_of_the_layers}, the folder is empty. ')

		with self._report:
			with tags.section():
				tags.h2('Layers')
				with tags.div():
					tags.span('To precisely measure the layers you can open the SVG files located in ')
					tags.a(f'{path_to_folder_with_SVG_files_of_the_layers.relative_to(self.path_to_PCB_report)}', href=path_to_folder_with_SVG_files_of_the_layers.relative_to(self.path_to_PCB_report))
					tags.span(' with a graphics software, for example with ')
					tags.a('Inkscape', href='https://inkscape.org/')
					tags.span('.')
				with tags.div(cls='multi_row_gallery'):
					for p in (path_to_folder_with_SVG_files_of_the_layers).iterdir():
						with tags.div():
							layer_name = p.stem.replace(f'{self.KiCad_project_name}-', '')
							tags.div(layer_name)
							tags.img(src=p.relative_to(self.path_to_PCB_report), title=str(p.relative_to(self.path_to_PCB_report)), alt=layer_name)
							metric_scale_bar(50)

	def _include_drills(self):
		path_where_to_place_drill_info = self.path_to_PCB_report_data/'drill'
		path_where_to_place_drill_info.mkdir(parents=True)

		# Export drill info:
		subprocess.run(
			[
				'kicad-cli', 'pcb',
				'export', 'drill',
				str(self.path_to_KiCad_pcb_file),
				'--output', str(path_where_to_place_drill_info),
				'--generate-map',
				'--map-format', 'svg',
				'--excellon-separate-th',
			]
		)

		with self._report:
			with tags.section():
				tags.h2('Drills')
				with tags.div():
					tags.span('More information and formats available in folder ')
					tags.a(f'{path_where_to_place_drill_info.relative_to(self.path_to_PCB_report)}', href=path_where_to_place_drill_info.relative_to(self.path_to_PCB_report))
					tags.span('.')
				with tags.div(cls='multi_row_gallery'):
					for p in (path_where_to_place_drill_info).iterdir():
						if p.suffix != '.svg':
							continue
						# Use Inkscape to remove annoying margin from SVG drawings:
						subprocess.run(
							[
								'inkscape',
								'--export-area-drawing',
								str(p),
								'-o', str(p),
							]
						)
						with tags.div():
							drills_name = p.stem.replace(f'{self.KiCad_project_name}-', '')
							tags.div(drills_name)
							tags.img(src=p.relative_to(self.path_to_PCB_report), title=str(p.relative_to(self.path_to_PCB_report)), alt=drills_name)

	def _include_physical_stackup(self):
		path_to_folder_where_I_expect_to_find_the_physical_stackup = self.path_to_PCB_report_data/'physical stackup'

		path_to_folder_where_I_expect_to_find_the_physical_stackup.mkdir(parents=True)
		input(f'⚠️  Please go to the KiCad PCB and make a screenshot of the physical stackyp, and save it into {path_to_folder_where_I_expect_to_find_the_physical_stackup}. Once you are done, press enter here. (Sorry, still don\'t know how to automate this step.) ')

		with self._report:
			with tags.section():
				tags.h2('Physical stackup')
				with tags.div(cls='multi_row_gallery'):
					for p in path_to_folder_where_I_expect_to_find_the_physical_stackup.iterdir():
						tags.img(src=p.relative_to(self.path_to_PCB_report), cls='picture')

	def _include_3D_model(self):
		path_to_folder_where_I_expect_to_find_images_of_the_3D_model = self.path_to_PCB_report_data/'3D/img'
		path_to_folder_where_I_expect_to_find_the_3D_models = self.path_to_PCB_report_data/'3D/model'

		path_to_folder_where_I_expect_to_find_images_of_the_3D_model.mkdir(parents=True)
		# ~ input(f'⚠️  Please go to the KiCad PCB and manually do some nice screenshots of the 3D model, and put them in {path_to_folder_where_I_expect_to_find_images_of_the_3D_model}. Once you are done, press enter here. (Sorry, still don\'t know how to automate this step.) ')

		for i,cammera_angle in enumerate([(-45,0,-45),(0,0,0)]):
			cmd = [
				'kicad-cli-nightly',
				'pcb', 'render',
				'--output', str(path_to_folder_where_I_expect_to_find_images_of_the_3D_model/f'{i}.png'),
				'--rotate', f"'{cammera_angle}'".replace('(','').replace(')','').replace(' ',''),
				'--zoom', '.7',
				'--width', '1111',
				'--height', '1111',
				'--floor',
				str(self.path_to_KiCad_pcb_file),
			]
			subprocess.run(cmd)

		path_to_folder_where_I_expect_to_find_the_3D_models.mkdir(parents=True)

		export_commands = dict(
			vrml = [
				'kicad-cli', 'pcb',
				'export', 'vrml',
				str(self.path_to_KiCad_pcb_file),
				'--output', f'{path_to_folder_where_I_expect_to_find_the_3D_models}/{self.KiCad_project_name}.wrl',
				'--units', 'mm',
			],
			step = [
				'kicad-cli', 'pcb',
				'export', 'step',
				str(self.path_to_KiCad_pcb_file),
				'--output', f'{path_to_folder_where_I_expect_to_find_the_3D_models}/{self.KiCad_project_name}.step',
			]
		)
		for format_name, cmd in export_commands.items():
			subprocess.run(cmd)

		for p in [path_to_folder_where_I_expect_to_find_images_of_the_3D_model,path_to_folder_where_I_expect_to_find_the_3D_models]:
			if len(list(p.iterdir())) == 0:
				raise RuntimeError(f'{p} is empty. ')

		with self._report:
			with tags.section():
				tags.h2('3D model')

				# Links to 3D models:
				with tags.div(cls='multi_row_gallery'):
					for p in path_to_folder_where_I_expect_to_find_the_3D_models.iterdir():
						tags.a(p.name, href=p.relative_to(self.path_to_PCB_report), cls='button_like')

				# Gallery with images of the 3D model:
				with tags.div(cls='multi_row_gallery'):
					for p in path_to_folder_where_I_expect_to_find_images_of_the_3D_model.iterdir():
						tags.img(src=p.relative_to(self.path_to_PCB_report), style='max-width: 333px;', cls='picture')

	def generate_report(self):
		self.path_to_PCB_report.mkdir()

		with self._report.head:
			tags.style('''
			body {
				max-width: 1111px;
				margin: auto;
				padding: 11px;
			}
			.picture {
				border-radius: 11px;
				max-width: 100%;
			}
			.multi_row_gallery {
				display: flex;
				flex-wrap: wrap;
				gap: 22px;
				row-gap: 22px;
				flex-direction: row;
				align-items: flex-start;
			}
			.button_like {
				outline: none;
				border: 0;
				padding: 11px;
				border-radius: 11px;
				background-color: rgb(222,222,222);
				font-family: inherit;
				font-size: 88%;
				text-decoration: none;
				color: inherit;
			}
			section {
				display: flex;
				flex-direction: column;
				gap: 11px;
				margin-top: 33px;
				margin-bottom: 33px;
			}
			h2:after {
				content:' ';
				display:block;
				border: .5px solid rgb(155,155,155);
			}

			''')

		with self._report:
			tags.h1(self.KiCad_project_name)

		self._include_3D_model()
		self._include_SVG_layers()
		self._include_drills()
		self._include_physical_stackup()

		path_to_report = self.path_to_PCB_report/'PCB_report.html'
		with open(path_to_report, 'w') as ofile:
			print(self._report, file=ofile)

		print(f'Report was saved in {path_to_report}')

if __name__ == '__main__':
	import argparse

	parser = argparse.ArgumentParser(
		prog = 'PCB_report',
		description = 'Create an HTML report from a KiCad PCB',
	)
	parser.add_argument('KiCad_project')

	args = parser.parse_args()

	report_generator = PCBReportGenerator(
		path_to_KiCad_project = Path(args.KiCad_project),
	)

	report_generator.generate_report()
