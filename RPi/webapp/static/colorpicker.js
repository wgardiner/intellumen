$.widget( "custom.colorpicker", {
    _create: function() {
    	var self = this; // So we'll have self available even if this is redefined.
    
        if(self.options.callback)
            self.callback = $.throttle(200, self.options.callback);

		self._colors = {};
		self._elms = {};
    	$.each(self.options.colors, function (idx, color) {
    		self._colors[color.slug] = clone(color);
    	})
        
        var master = $("<div/>");
        master.addClass("master");

    	var table = $("<table/>");
        table.addClass("colorTable");
    	master.append(table);

        var splotch = $("<div/>");
        splotch.addClass("colorSplotch");
        master.append(splotch);

        self.element.append(master);

        var recalculateSplotch = function() { 
            var rgb = [0,0,0];
            var weightSum = 0;
            $.each(self._colors, function (_, color) {
                weightSum += color.weight;
                $.each( hexToRgb(color.hex), function (idx, rgbVal) {
                    rgb[idx] = rgb[idx] + rgbVal * color.value * color.weight;
                });
            });

            var ratio = Math.max.apply(Math, rgb) / 255;
            rgb = $.map(rgb, function(val) { 
                return ratio != 0 ? Math.round(val / ratio) : 0; 
            });

            var newColor = "#" + rgbToHex(rgb);
            splotch.css('background', newColor);
        };

        recalculateSplotch();

    	$.each(self._colors, function (idx, color) {
    		// Build the DOM (tr with 3 td, [label, slider, input])
    		var tr = $("<tr/>");

    		var label = $("<label/>");
    		label.text(color.name);
	   		label.addClass("label");
    		tr.append($("<td/>").addClass("label-td").append(label));

    		var slider = $("<div/>");
    		slider.addClass("slider");
    		slider.slider({
	            orientation: "horizontal",
	            range: "min",
	            max: 255,
	            value: color.value
	        });

    		slider.children(".ui-slider-range, .ui-slider-handle").css("background", "#" + color.hex);

	        tr.append($("<td/>").addClass("slider-td").append(slider));

	        var input = $("<input max='255' type='text'/>");
	        input.addClass("input");
	        input.val(color.value);
	        tr.append($("<td/>").addClass("input-td").append(input));

	        self._elms[color.slug] = {input: input, slider: slider};

	        table.append(tr);

            self._justChanged = false;

	        // Create the slider onChange function
	        var sliderChanged = function() {
	        	// `this` is redefined as the slider here
	        	var val = slider.slider("value");
	        	var oldVal = self._colors[color.slug].value;
	        	self._colors[color.slug].value = val;
	        	input.val(val);
    
                recalculateSplotch();

	        	if(self.callback && val != oldVal) {
	        		self.callback(self.colors(), self._colors);
	        	}

                // mark as "just changed" for 100ms to avoid feedback loops
                self._justChanged = true;
                window.setTimeout(function() { self._justChanged = false; }, 100);
	        };

	        // Create the input onChange function
	        var inputChanged = function() {
	        	// `this` is redefined as the input here
	        	var val = input.val();
	        	var oldVal = self._colors[color.slug].value;
	        	self._colors[color.slug].value = val;
	        	slider.slider("value", val);

                recalculateSplotch();
	        	
                //slider.slider("refresh");
	        	if(self.callback && val != oldVal) {
	        		self.callback(self.colors(), self._colors);
	        	}

                // mark as "just changed" for 100ms to avoid feedback loops
                self._justChanged = true;
                window.setTimeout(function() { self._justChanged = false; }, 100);
	        };

	        // Wire the slider to the input and vice versa
	        slider.slider('option', 'slide', sliderChanged);
	        slider.slider('option', 'change', sliderChanged);
	        input.change(inputChanged);
	        input.keyup(inputChanged);
    	});

		if (self.options.submit) {
			self.element.append($("<button/>").text("Submit").click(function() {
				self.options.submit(self.colors(), self._colors);
			}));
		}
    },

    // Dumps the whole internal color datatype, but can't be used as a setter
    colorData: function() {
    	// Can only act as a getter
    	return this._colors;
    },

    // Works with structure like: {slug: val, slug: val, ...} (e.g. {red: 211, blue: 200, green: 125, amber: 100})
    colors: function( colors ) {
    	// No value passed, act as a getter.
    	if (colors === undefined) {
    		var colvals = {};
    		for (var slug in this._colors) {
    			colvals[slug] = this._colors[slug].value;
    		}
    		return colvals;
    	}

    	// Value passed, act as a setter
    	var changed = false;
    	for (var slug in colors) {
    		var newColor = colors[slug];
    		var currentColor = this._colors[slug];
    		if (this._colors[slug] !== undefined && newColor !== undefined) {
    			this._colors[slug].value = newColor;
    			this._elms[slug].slider.slider('value', newColor);
    			this._elms[slug].input.val(newColor);
    		}
    	}
    }
});
