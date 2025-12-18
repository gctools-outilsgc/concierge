var webpack = require("webpack");
var MiniCssExtractPlugin = require("mini-css-extract-plugin");
var BundleTracker = require("webpack-bundle-tracker");
var autoprefixer = require("autoprefixer");
var path = require("path");

module.exports = {
    context: __dirname,
    entry: {
        web: [
            "./assets/js/Web.jsx"
        ]
    },
    output: {
        path: path.resolve("./assets/bundles/"),
        filename: "[name].js",
        chunkFilename: "[id].js"
    },
    module: {
        rules: [
            {
                test: /\.jsx$/,
                use: ["babel-loader"],
                exclude: /node_modules/
            },
            {
                test: /\.css$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    { loader: "css-loader" },
                    { loader: "postcss-loader" },
                ]
            },
            {
                test: /\.less$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    { loader: "css-loader" },
                    { loader: "postcss-loader" },
                    { loader: "less-loader" }
                ]
            },
            {
                test: /\.(ttf|eot|svg|woff(2)?)(\?[a-z0-9]+)?$/,
                use: "file-loader"
            }
        ]
    },
    devtool: "source-map",
    plugins: [
        new MiniCssExtractPlugin({
            filename: "[name].css"
        }),
        new BundleTracker({
            path: __dirname,
            filename: "webpack-stats.json"
        }),
        new webpack.LoaderOptionsPlugin({
            options: {
                postcss: [ autoprefixer() ]
            }
        }),
        new webpack.DefinePlugin({
            "process.env": {
                "NODE_ENV": JSON.stringify("production")
            }
        })
    ],
    resolve: {
        extensions: [".js", ".jsx"]
    }
}
