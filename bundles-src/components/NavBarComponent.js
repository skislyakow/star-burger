import React, { Component } from 'react';

import { formatPrice } from '../format';

class NavBarComponent extends Component {
  render() {
    const { totalItems, totalAmount } = this.props;
    const cartButtonLabel = totalItems
      ? `Корзина (${totalItems})`
      : 'Корзина';

    return (
      <nav className="navbar navbar-inverse navbar-fixed-top">
        <div className="container-fluid">
          <div className="navbar-header">
            <button
              type="button"
              className="navbar-toggle"
              data-toggle="collapse"
              data-target="#myNavbar"
            >
              <span className="icon-bar"></span>
              <span className="icon-bar"></span>
              <span className="icon-bar"></span>
            </button>
            <a className="navbar-brand" href="#">
              Star Burger
            </a>
          </div>
          <div>
            <div className="collapse navbar-collapse" id="myNavbar">
              <ul className="nav navbar-nav">
                <li>
                  <a href="#menu">Меню</a>
                </li>
                <li>
                  <a href="#contact_us">Контакты</a>
                </li>
              </ul>
              <ul className="nav navbar-nav navbar-right">
                <li>
                  <a href="#menu">
                    Блюд в заказе: {totalItems || ''}
                  </a>
                </li>
                <li>
                  <a
                    href="#menu"
                    className={totalAmount ? 'currency' : ''}
                  >
                    Стоимость: {totalAmount ? formatPrice(totalAmount) : ''}
                  </a>
                </li>
                <li style={{ float: 'right' }}>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={this.props.handleCartShow}
                  >
                    <span className="glyphicon glyphicon-shopping-cart"></span>{' '}
                    {cartButtonLabel}
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </nav>
    );
  }
}

export default NavBarComponent;
