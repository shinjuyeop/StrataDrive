from pathlib import Path
import json
import hashlib
from PIL import Image, ImageDraw, ImageFont

root = Path('build/m10-model-screen-v1')
frozen = json.loads((root / 'freeze.json').read_text())
models = frozen['candidates']
classes = {0: 'person', 1: 'bicycle', 2: 'car', 3: 'motor', 5: 'bus', 7: 'truck'}
runs = {m: json.loads((root / f'{m}-run.json').read_text()) for m in models}
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
panels = []
for key, spec in frozen['datasets'].items():
    data = Path(spec['path'])
    rgb, gt, meta = [json.loads((data / name).read_text()) for name in ('rgb.json', 'evaluation-only-gt.json', 'benchmark.json')]
    indices = [next(i for i, scene in enumerate(meta['scenes']) if scene['stratum'] == stratum and scene['target_class'] == cls) for stratum, cls in [('near', 0), ('far', 0), ('far', 7), ('occluded', 5)]]
    panel = Image.new('RGB', (1600, 1050), '#15202b')
    draw = ImageDraw.Draw(panel)
    draw.text((8, 8), f'{key}: consumed DEVELOPMENT only. Cyan=visible GT; green=predictions. Posthoc diagnostic; no gate changes.', font=font, fill='white')
    for column, name in enumerate(models):
        draw.text((column * 320 + 5, 34), name, font=font, fill='white')
    for rownum, index in enumerate(indices):
        source, truth, scene = rgb['frames'][index], gt['frames'][index], meta['scenes'][index]
        raw = (data / source['rgb_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source['rgb_sha256']
        for column, name in enumerate(models):
            image = Image.frombytes('RGB', (640, 384), raw)
            paint = ImageDraw.Draw(image)
            for obj in truth['objects']:
                box = obj['box']
                paint.rectangle(box, outline='cyan', width=2)
            prediction = next(r for r in runs[name]['rows'] if r['dataset'] == key and r['scene'] == source['scene'])
            for obj in prediction['detections']:
                box = obj['box']
                paint.rectangle(box, outline='#70ff50', width=2)
                paint.text((box[0], max(0, box[1] - 15)), f"{classes[obj['class_id']]} {obj['score']:.2f}", font=font, fill='#70ff50', stroke_width=1, stroke_fill='black')
            panel.paste(image.resize((320, 192)), (column * 320, 70 + rownum * 244))
            draw.text((column * 320 + 5, 264 + rownum * 244), f"{scene['stratum']} {classes[scene['target_class']]}; {scene['weather']}", font=small, fill='white')
            draw.text((column * 320 + 5, 281 + rownum * 244), source['scene'], font=small, fill='white')
    path = root / f'{key}-comparison.png'
    panel.save(path)
    panels.append(dict(dataset=key, indices=indices, scenes=[rgb['frames'][i]['scene'] for i in indices], path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(root / 'visual-panels.json').write_text(json.dumps(dict(scope='posthoc fixed scene types, first case per type; development only', panels=panels), indent=2) + '\n')
print('Rendered', len(panels), 'panels')
