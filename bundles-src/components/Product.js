import React, { Component } from 'react';
import Counter from './Counter';
import { formatPrice } from '../format';

class Product extends Component {
  state = {
    isAdded: false,
    quantity: 1,
  };

  componentWillUnmount() {
    clearTimeout(this.resetTimer);
  }

  updateQuantity(quantity) {
    this.setState({ quantity });
  }

  addToCart(quantity) {
    this.props.addToCart({
      ...this.props.product,
      quantity,
    });

    this.setState({ isAdded: true });

    clearTimeout(this.resetTimer);
    this.resetTimer = setTimeout(() => {
      this.setState({ quantity: 1, isAdded: false });
    }, 1500);
  }

  quickView() {
    this.props.openModal(this.props.product);
  }

  render() {
    const { image, name, price } = this.props.product;

    return (
      <div className="product">
        <div className="product-image">
          <img src={image} alt={name} onClick={this.quickView.bind(this)} />
        </div>
        <h4 className="product-name">{name}</h4>
        <p className="product-price currency">{formatPrice(price)}</p>
        <Counter
          quantity={this.state.quantity}
          updateQuantity={(quantity) => this.updateQuantity(quantity)}
        />
        <div className="product-action">
          <button
            className={
              !this.state.isAdded ? 'btn btn-primary' : 'btn btn-success'
            }
            type="button"
            onClick={(event) => this.addToCart(this.state.quantity)}
          >
            {!this.state.isAdded ? 'В корзину' : '✔ Добавлено'}
          </button>
        </div>
      </div>
    );
  }
}

export default Product;
