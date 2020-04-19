import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  IDisposable, DisposableDelegate
} from '@lumino/disposable';

import {
  ToolbarButton
} from '@jupyterlab/apputils';

import {
  DocumentRegistry
} from '@jupyterlab/docregistry';

import {
  NotebookActions, NotebookPanel, INotebookModel
} from '@jupyterlab/notebook';

export
class ButtonExtension implements DocumentRegistry.IWidgetExtension<NotebookPanel, INotebookModel> {
  /**
   * Create a new extension object.
   */
  createNew(panel: NotebookPanel, context: DocumentRegistry.IContext<INotebookModel>): IDisposable {
    let callback = () => {
      NotebookActions.runAll(panel.content, context.sessionContext);
    };
    let button = new ToolbarButton({
      className: 'myButton',
      // iconClass: 'fa fa-fast-forward',
      label: 'Validate',
      onClick: callback,
      tooltip: 'Validate Assignment'
    });

    let children = panel.toolbar.children();
    let index = 0;
    for (let i = 0; ; i++) {
        let widget = children.next();
        if (widget == undefined) {
            break;
        }
        if (widget.node.classList.contains("jp-Toolbar-spacer")) {
            index = i;
            break;
        }
    }
    panel.toolbar.insertItem(index, 'runAll', button);
    return new DisposableDelegate(() => {
      button.dispose();
    });
  }
}

/**
 * Initialization data for the validate_assignment extension.
 */
const extension: JupyterFrontEndPlugin<void> = {
  id: 'validate_assignment',
  autoStart: true,
  requires: [],
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension validate_assignment is activated!');

    app.docRegistry.addWidgetExtension('Notebook', new ButtonExtension());
  }
};

export default extension;
