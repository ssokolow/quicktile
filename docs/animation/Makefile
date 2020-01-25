svgs := $(wildcard svg/*.svg)
pngs := $(patsubst svg/%.svg,png/%.png,$(svgs))

.PHONY: all

all: animation.gif

animation.gif: $(pngs)
	# Ensure the order is correct in Geeqie's "by date" sorting
	find png/ -iname '*.png' | sort | xargs touch

	# Convert with alpha removal to avoid jaggies on the curves
	convert -delay 100 png/*.png -alpha remove -alpha off animation.gif
	gifsicle --batch -O3 animation.gif

png/%.png: svg/%.svg | png
	inkscape $< --export-png=$@

png:
	mkdir -p $@

.PHONY: clean
clean:
	rm -rf png
	rm animation.gif
