const dark = { fit: "contain", background: "#0b0b0c" };

export default {
  headLinkOptions: { preset: "2023" },
  preset: {
    transparent: { sizes: [64, 192, 512], favicons: [[48, "favicon.ico"]] },
    maskable: { sizes: [512], resizeOptions: dark },
    apple: { sizes: [180], resizeOptions: dark },
  },
  images: ["public/favicon.svg"],
};
