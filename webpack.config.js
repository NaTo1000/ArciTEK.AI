const path = require('path');

module.exports = {
  entry: './arcitek_ui/web/app.js',
  output: {
    filename: 'app.js',
    path: path.resolve(__dirname, 'arcitek_ui/web/dist'),
    clean: true,
  },
  devServer: {
    static: './arcitek_ui/web',
    port: 8080,
    proxy: [
      {
        context: ['/api'],
        target: 'http://127.0.0.1:8000',
      },
    ],
  },
};
