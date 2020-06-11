import React, { Component } from 'react';
import logo from './logo.svg';
import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';
import Amplify, {API,graphqlOperation,Auth} from 'aws-amplify';
import { withAuthenticator} from 'aws-amplify-react'; 
import aws_exports from './aws-exports'; // specify the location of aws-exports.js file on your project
import { listNotes } from './graphql/queries';
import { deleteNote, createNote, updateNote } from './graphql/mutations';
Amplify.configure(aws_exports);

class App extends Component {
  constructor(props){
    super(props);
    this.state={
      id:"",
      notes:[],
      value:"",
      displayAdd:true,
      displayUpdate:false
    };
    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
    this.handleUpdate = this.handleUpdate.bind(this);
  }

  async componentDidMount(){
    const notes = await API.graphql(graphqlOperation(listNotes));

    this.setState({
      notes: notes.data.listNotes.items,
      userId: (await Auth.currentSession()).getIdToken().payload["cognito:username"]
    });
     
  }

  handleChange(event) {
    this.setState({value:event.target.value});
  }
  async handleSubmit(event) {
    event.preventDefault();
    event.stopPropagation();
    const note = {"note":this.state.value}
    await API.graphql(graphqlOperation(createNote, { input: note }));
    this.listNotes();
    this.setState({value:""});
  }
  async handleDelete(id) {
    const noteId = {"id":id};
    await API.graphql(graphqlOperation(deleteNote, { input: noteId }));
    this.listNotes();
  }
  async handleUpdate(event) {
    event.preventDefault();
    event.stopPropagation();
    const note = {"id":this.state.id,"note":this.state.value};
    await API.graphql(graphqlOperation(updateNote, { input: note }));
    this.listNotes();
    this.setState({displayAdd:true,displayUpdate:false,value:""});
  }
  selectNote(note){
    this.setState({id:note.id,value:note.note,displayAdd:false,displayUpdate:true});
  }
  async listNotes(){
    const notes = await API.graphql(graphqlOperation(listNotes));
    this.setState({notes:notes.data.listNotes.items});
  }
  
  render() {
    const data = [].concat(this.state.notes)
      .map((item,i)=> {
        if (item.owner === this.state.userId) {
          return (<div key={item.id} className="alert alert-primary alert-dismissible show" role="alert">
            <span key={item.i} onClick={this.selectNote.bind(this, item)}>{item.note}</span>
            <button key={item.i} type="button" className="close" data-dismiss="alert" aria-label="Close" onClick={this.handleDelete.bind(this, item.id)}>
              <span aria-hidden="true">&times;</span>
            </button>
          </div>)
        }
        else {
          return (<div key={item.id} className="alert alert-primary alert-dismissible show" role="alert">
            <span key={item.i}>{item.note}</span>
          </div>)
        }
      }
      
      )
    return (
      <div className="App">
        <header className="App-header">
          <img src={logo} className="App-logo" alt="logo" />
          <h1 className="App-title">Pulumi Notes App</h1>
        </header>
        <br/>
        <div className="container">
          {this.state.displayAdd ?
            <form onSubmit={this.handleSubmit}>
              <div className="input-group mb-3">
                <input type="text" className="form-control form-control-lg" placeholder="New Note" aria-label="Note" aria-describedby="basic-addon2" value={this.state.value} onChange={this.handleChange}/>
                <div className="input-group-append">
                  <button className="btn btn-primary" type="submit">Add Note</button>
                </div>
              </div>
            </form>
          : null }
          {this.state.displayUpdate ?
            <form onSubmit={this.handleUpdate}>
              <div className="input-group mb-3">
                <input type="text" className="form-control form-control-lg" placeholder="Update Note" aria-label="Note" aria-describedby="basic-addon2" value={this.state.value} onChange={this.handleChange}/>
                <div className="input-group-append">
                  <button className="btn btn-primary" type="submit">Update Note</button>
                </div>
              </div>
            </form>
          : null }
        </div>
        <br/>
        <div className="container">
          {data}
        </div>
      </div>
    );
  }
}
export default withAuthenticator(App, { includeGreetings: true });
