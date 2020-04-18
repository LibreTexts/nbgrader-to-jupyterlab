# jupyterlab_apod

Show a random NASA Astronomy Picture of the Day in a JupyterLab panel

From https://github.com/jupyterlab/jupyterlab_apod

## Requirements

* JupyterLab >= 1.0

## Install

<del>`jupyter labextension install jupyterlab_apod`</del>

## Contributing

### Install

The `jlpm` command is JupyterLab's pinned version of
[yarn](https://yarnpkg.com/) that is installed with JupyterLab. You may use
`yarn` or `npm` in lieu of `jlpm` below.

1. Clone this repo
2. Move to `jupyterlab_apod` directory
	(`nbgrader/labextensions/jupyterlab_apod/`)
3. Install
```bash
# Install dependencies
jlpm
# Build Typescript source
jlpm build
# Link your development version of the extension with JupyterLab
jupyter labextension link .
```

### Update
After making changes:
```bash
# Rebuild Typescript source after making changes
jlpm build
# Rebuild JupyterLab after making any changes
jupyter lab build
```

You can watch the source directory and run JupyterLab in watch mode to watch for changes in the extension's source and automatically rebuild the extension and application.

```bash
# Watch the source directory in another terminal tab
jlpm watch
# Run jupyterlab in watch mode in one terminal tab
jupyter lab --watch
```

### Uninstall

```bash
jupyter labextension uninstall jupyterlab_apod
```

