svgs := $(wildcard svg/*.svg)
pngs := $(patsubst svg/%.svg,png/%.png,$(svgs))

.PHONY: all
all: $(pngs)

png/%.png: svg/%.svg | png
	convert -background none $< $@

png:
	mkdir -p $@

.PHONY: clean
clean:
	rm -rf png
