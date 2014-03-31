function hexToRgb(hex) {
    // Convert hex color string (no #) to RGB list
    if (hex.length != 6) {
        alert("Error: hex string is invalid. " + hex);
    }
    return [parseInt(hex.slice(0,2), 16), parseInt(hex.slice(2,4), 16), parseInt(hex.slice(4,6), 16)];
}

function dec2hex(i) {
    return (i+0x100).toString(16).substr(-2).toUpperCase();
}

function rgbToHex(rgb) {
    // Convert 3-elm array to 6-char hex string
    return dec2hex(rgb[0]) + dec2hex(rgb[1]) + dec2hex(rgb[2]);
}

function clone(obj) {
    // Handle the 3 simple types, and null or undefined
    if (null == obj || "object" != typeof obj) return obj;

    // Handle Date
    if (obj instanceof Date) {
        var copy = new Date();
        copy.setTime(obj.getTime());
        return copy;
    }

    // Handle Array
    if (obj instanceof Array) {
        var copy = [];
        for (var i = 0, len = obj.length; i < len; i++) {
            copy[i] = clone(obj[i]);
        }
        return copy;
    }

    // Handle Object
    if (obj instanceof Object) {
        var copy = {};
        for (var attr in obj) {
            if (obj.hasOwnProperty(attr)) copy[attr] = clone(obj[attr]);
        }
        return copy;
    }

    throw new Error("Unable to copy obj! Its type isn't supported.");
}
