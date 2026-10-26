import React, { Component } from 'react';
import { Modal } from 'react-bootstrap';
import { Button } from 'react-bootstrap';

class CheckoutModal extends Component {
  state = {
    firstname: '',
    lastname: '',
    phonenumber: '',
    address: '',
    waitTillCheckoutEnds: false,
  };

  saveField = (field) => (event) => {
    this.setState({ [field]: event.target.value });
  };

  async submit(event) {
    event.preventDefault();
    this.setState({ waitTillCheckoutEnds: true });

    try {
      const saved = await this.props.handleCheckout(this.state);

      if (saved) {
        this.setState({
          firstname: '',
          lastname: '',
          phonenumber: '',
          address: '',
        });
      }
    } finally {
      this.setState({ waitTillCheckoutEnds: false });
    }
  }

  render() {
    return (
      <Modal
        show={this.props.checkoutModalActive}
        onHide={this.props.handleCheckoutModalClose}
      >
        <form onSubmit={(event) => this.submit(event)}>
          <Modal.Header closeButton>
            <h2>
              <center>
                <Modal.Title>Оформление заказа</Modal.Title>
              </center>
            </h2>
          </Modal.Header>
          <Modal.Body>
            {this.props.error && (
              <div className="alert alert-danger" role="alert">
                {this.props.error}
              </div>
            )}

            <div className="form-group container-fluid">
              <label htmlFor="firstname">Имя:</label>
              <input
                onChange={this.saveField('firstname')}
                value={this.state.firstname}
                required
                id="firstname"
                type="text"
                autoComplete="given-name"
                className="form-control"
              />
              <br />
              <label htmlFor="lastname">Фамилия:</label>
              <input
                onChange={this.saveField('lastname')}
                value={this.state.lastname}
                required
                id="lastname"
                type="text"
                autoComplete="family-name"
                className="form-control"
              />
              <br />
              <label htmlFor="phonenumber">Телефон:</label>
              <input
                onChange={this.saveField('phonenumber')}
                value={this.state.phonenumber}
                required
                id="phonenumber"
                maxLength="20"
                type="tel"
                autoComplete="tel"
                className="form-control"
                placeholder="+7 901 ..."
              />
              <br />
              <label htmlFor="address">Адрес доставки:</label>
              <input
                onChange={this.saveField('address')}
                value={this.state.address}
                required
                id="address"
                type="text"
                maxLength="256"
                autoComplete="street-address"
                className="form-control"
                placeholder="Город, улица, дом"
              />
              <br />
            </div>
          </Modal.Body>
          <Modal.Footer>
            <Button
              id="order-submit-btn"
              className="btn btn-primary"
              type="submit"
              disabled={this.state.waitTillCheckoutEnds}
            >
              Отправить
            </Button>
            <Button onClick={this.props.handleCheckoutModalClose}>
              Закрыть
            </Button>
          </Modal.Footer>
        </form>
      </Modal>
    );
  }
}

export default CheckoutModal;
