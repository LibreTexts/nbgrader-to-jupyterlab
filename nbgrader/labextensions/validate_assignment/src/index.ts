import {
  JupyterFrontEnd, JupyterFrontEndPlugin
} from '@jupyterlab/application';

import {
  ICommandPalette, MainAreaWidget
} from '@jupyterlab/apputils';

import {
  Cell
} from '@jupyterlab/cells';

import {
  INotebookTracker
} from '@jupyterlab/notebook';

import {
  Widget, Panel
} from '@lumino/widgets';

// validate_assignment
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


class NbgraderCellToolbar extends Widget {
  cell : Cell;
  cellId  : HTMLDivElement;
  grade : HTMLDivElement;
  type : HTMLSelectElement;

  constructor(cell: Cell) {
    super();
    this.cell = cell;
    this._initNode();
  }

  _initNode() {
      const header = this.cell.node.getElementsByClassName('jp-CellHeader')[0] as HTMLDivElement;
      header.appendChild(this.node);
      header.style.height = 'auto';
      this.node.classList.add('nbgrader-CellToolbar');
      this.type = document.createElement('select');
      this.cellId = document.createElement('div');
      this.grade = document.createElement('div');
      const typeOptions = [
        {'value': 'none', 'text': '-'},
        {'value': 'manual-answer', 'text': 'Manually graded answer'},
        {'value': 'manual-task', 'text': 'Manually graded task'},
        {'value': 'auto-answer', 'text': 'Autograded answer'},
        {'value': 'auto-task', 'text': 'Autograded task'},
        {'value': 'read-only', 'text': 'Read-only'},
      ];
      for (const typeOption of typeOptions) {
        const option = document.createElement('option');
        option.value = typeOption['value'];
        option.innerHTML = typeOption['text'];
        this.type.appendChild(option);
      }
      this.type.onchange = this._onTypeChangedFunction();
      var input = document.createElement('input');
      input.type = 'text';
      input.defaultValue = '<cell ID here>';
      this.cellId.innerHTML = 'ID: ';
      this.cellId.appendChild(input);
      input = document.createElement('input');
      input.type = 'number';
      input.defaultValue = '0';
      this.grade.innerHTML = 'Grade: ';
      this.grade.appendChild(input);
      this.node.appendChild(this.grade);
      this.node.appendChild(this.cellId);
      this.node.appendChild(this.type);
  }

  _onTypeChangedFunction() {
    var self = this;
    return function() {
      console.log('Type changed to ' + self.type.value);
      if (self.type.value == 'none') {
        self.cell.model.metadata.delete('type');
        return;
      }
      self.cell.model.metadata.set('type', self.type.value);
    }
  }
}

function mainAreaWidget(label: string, id: string, content: Widget) : MainAreaWidget {
  const widget = new MainAreaWidget({content});
  widget.title.label = label;
  widget.title.closable = true;
  widget.id = id;
  return widget;
}

function assignmentsWidget() : MainAreaWidget {
  const content = new Widget();
  const widget = mainAreaWidget('nbgrader | Assignments', 'nbgrader-assignments', content);

  var iframe = document.createElement('iframe');
  iframe.src = '/tree#assignments';
  iframe.width = '100%';
  iframe.height = '100%';
  iframe.style.border = '0';
  content.node.append(iframe);

  return widget;
}

function coursesWidget() : MainAreaWidget {
  const content = new Widget();
  const widget = mainAreaWidget('nbgrader | Courses', 'nbgrader-courses', content);

  var iframe = document.createElement('iframe');
  iframe.src = '/tree#courses';
  iframe.width = '100%';
  iframe.height = '100%';
  iframe.style.border = '0';
  content.node.append(iframe);

  return widget;
}

function formgraderWidget() : MainAreaWidget {
  const content = new Widget();
  const widget = mainAreaWidget('nbgrader | Formgrade', 'nbgrader-formgrader', content);

  var iframe = document.createElement('iframe');
  iframe.src = '/formgrader';
  iframe.width = '100%';
  iframe.height = '100%';
  iframe.style.border = '0';
  content.node.append(iframe);

  return widget;
}

function shellActivateFunction(app: JupyterFrontEnd, widget: Widget, loc: string) {
  return () => {
    if (!widget.isAttached) {
      app.shell.add(widget, loc);
    }
    app.shell.activateById(widget.id);
  }
}

function nbgraderHtmlObj(app: JupyterFrontEnd) {
  let container = document.createElement('div');
  let header = document.createElement('h1');
  let formgrader = document.createElement('p');
  let courses = document.createElement('p');
  let assignments = document.createElement('p');

  header.innerHTML = 'nbgrader';

  var a = document.createElement('a');
  a.innerHTML = 'Formgrader';
  a.onclick = shellActivateFunction(app, formgraderWidget(), 'main');
  formgrader.append(a);

  a = document.createElement('a');
  a.innerHTML = 'Courses';
  a.onclick = shellActivateFunction(app, coursesWidget(), 'main');
  courses.append(a);

  a = document.createElement('a');
  a.innerHTML = 'Assignments';
  a.onclick = shellActivateFunction(app, assignmentsWidget(), 'main');
  assignments.append(a);

  container.append(header);
  container.append(formgrader);
  //container.append(courses);
  //container.append(assignments);

  let tree = document.createElement('iframe');
  tree.src = '/tree';
  container.append(tree);
  container.append(tree);

  return container;
}

function activateLeftPanel(app: JupyterFrontEnd) {
  const widget = new Panel();
  widget.id = 'nbgrader-menu';
  widget.title.label = 'nbgrader';
  widget.node.appendChild(nbgraderHtmlObj(app));
  app.shell.add(widget, 'left');
}

function _onActiveCellChangedFunction(tracker: INotebookTracker) {
  return function() {
    const cell = tracker.activeCell;
    console.log(cell.node);
  }
}

function _onCurrentChangedFunction(tracker: INotebookTracker) {
  return function() {
    const notebook = tracker.currentWidget ? tracker.currentWidget.content : null;
    if (notebook == null) {
      return;
    }
    for (const cell in notebook.widgets) {
      const header = notebook.widgets[cell].node.getElementsByClassName('jp-CellHeader')[0] as HTMLDivElement;
      if (header.getElementsByClassName('nbgrader-CellToolbar').length) {
        continue;
      }
      new NbgraderCellToolbar(notebook.widgets[cell]);
    }
  }
}

function trackNotebook(tracker: INotebookTracker) {
  tracker.activeCellChanged.connect(_onActiveCellChangedFunction(tracker));
  tracker.currentChanged.connect(_onCurrentChangedFunction(tracker));
}

// validate_assignment
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
      iconClass: 'fa fa-fast-forward',
      onClick: callback,
      tooltip: 'Run All'
    });

    panel.toolbar.insertItem(0, 'runAll', button);
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
  requires: [ICommandPalette, INotebookTracker],
  activate: (app: JupyterFrontEnd, palette: ICommandPalette, notebookTracker:
             INotebookTracker) => {
    console.log('JupyterLab extension validate_assignment is activated!');

	// validate_assignment
	app.docRegistry.addWidgetExtension('Notebook', new ButtonExtension());

    // Create a blank content widget inside of a MainAreaWidget
    const content = new Widget();
    const widget = new MainAreaWidget({content});
    widget.id = 'apod2-jupyterlab';
    widget.title.label = 'Astronomy Picture';
    widget.title.closable = true;

    // Add an application command
    const command: string = 'apod2:open';
    app.commands.addCommand(command, {
      label: 'Random Astronomy Picture',
      execute: () => {
        if (!widget.isAttached) {
          // Attach the widget to the main work area if it's not there
          app.shell.add(widget, 'main');
        }
        // Activate the widget
        app.shell.activateById(widget.id);
      }
    });

    // Add the command to the palette.
    palette.addItem({command, category: 'Tutorial'});

    activateLeftPanel(app);
    trackNotebook(notebookTracker);
  }
};

export default extension;
