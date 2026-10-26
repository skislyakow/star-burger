import React, { Component } from 'react';
import _ from 'lodash';

import NavBarComponent from './components/NavBarComponent';
import CartModalComponent from './components/CartModalComponent';
import BannerComponent from './components/BannerComponent';
import Products from './components/Products';
import QuickView from './components/QuickView';
import FooterComponent from './components/FooterComponent';
import CheckoutModal from './components/CheckoutModalComponent';
import LoadingProducts from './components/loaders/LoadingProducts';
import NoResults from './components/NoResults';
import StatusBanner from './components/StatusBanner';

import { getBanners, getProducts, submitOrder } from './api';
import {
  addToCart,
  cartCount,
  cartTotal,
  removeFromCart,
  toOrderLines,
} from './cart';

import './css/App.css';

const STATUS_TIMEOUT = 8000;

class App extends Component {
  state = {
    banners: null, // null — баннеры ещё грузятся
    products: null, // null — меню ещё грузится
    productsError: false,
    term: '',
    cart: [],
    quickViewProduct: null,
    showCart: false,
    checkoutModalActive: false,
    checkoutError: null,
    status: null,
  };

  componentDidMount() {
    this.loadProducts();
    this.loadBanners();
  }

  componentWillUnmount() {
    clearTimeout(this.statusTimer);
  }

  loadProducts = async () => {
    this.setState({ products: null, productsError: false });

    try {
      const products = await getProducts();
      this.setState({ products });
    } catch (error) {
      this.setState({ productsError: true });
      this.showStatus('danger', error.message);
    }
  };

  loadBanners = async () => {
    try {
      const banners = await getBanners();
      this.setState({ banners });
    } catch (error) {
      // Без баннеров витрина работает — молча оставляем карусель пустой.
      this.setState({ banners: [] });
    }
  };

  showStatus = (kind, text) => {
    clearTimeout(this.statusTimer);
    this.setState({ status: { kind, text } });
    this.statusTimer = setTimeout(
      () => this.setState({ status: null }),
      STATUS_TIMEOUT,
    );
  };

  handleSearch = (event) => {
    this.setState({ term: event.target.value });
  };

  handleAddToCart = (product) => {
    this.setState(({ cart }) => ({ cart: addToCart(cart, product) }));
  };

  handleRemoveProduct = (productId, event) => {
    if (event) {
      event.preventDefault();
    }
    this.setState(({ cart }) => ({ cart: removeFromCart(cart, productId) }));
  };

  handleCartShow = () => {
    this.setState({ showCart: true });
  };

  handleCartClose = () => {
    this.setState({ showCart: false });
  };

  handleQuickViewModalShow = (product) => {
    this.setState({ quickViewProduct: product });
  };

  handleQuickViewModalClose = () => {
    this.setState({ quickViewProduct: null });
  };

  handleCheckoutModalShow = () => {
    this.setState({ checkoutModalActive: true, checkoutError: null });
  };

  handleCheckoutModalClose = () => {
    this.setState({ checkoutModalActive: false });
  };

  handleCheckout = async ({ firstname, lastname, phonenumber, address }) => {
    try {
      await submitOrder({
        firstname: firstname.trim(),
        lastname: lastname.trim(),
        phonenumber: phonenumber.trim(),
        address: address.trim(),
        products: toOrderLines(this.state.cart),
      });
    } catch (error) {
      this.setState({ checkoutError: error.message });
      return false;
    }

    this.setState({
      cart: [],
      showCart: false,
      checkoutModalActive: false,
      checkoutError: null,
    });
    this.showStatus(
      'success',
      'Заказ оформлен. Вам перезвонят в течение 10 минут.',
    );
    return true;
  };

  renderMenuSection(key, title, productList) {
    return (
      <div style={{ marginTop: '50px' }} className="form-group" key={key}>
        <center>
          <h2>{title}</h2>
          <hr />
        </center>

        <Products
          productsList={productList}
          addToCart={this.handleAddToCart}
          openModal={this.handleQuickViewModalShow}
        />
      </div>
    );
  }

  render() {
    const {
      banners,
      products,
      productsError,
      term,
      cart,
      quickViewProduct,
      showCart,
      checkoutModalActive,
      checkoutError,
      status,
    } = this.state;

    const normalizedTerm = _.lowerCase(_.trim(term));
    const totalItems = cartCount(cart);
    const totalAmount = cartTotal(cart);
    const menuBlocks = [];

    if (products) {
      let filteredProducts = products;

      if (normalizedTerm) {
        filteredProducts = products.filter((product) =>
          product.name.toLowerCase().includes(normalizedTerm),
        );
      } else {
        const highlightedProducts = products.filter(
          (product) => product.special_status,
        );

        if (highlightedProducts.length) {
          menuBlocks.push(
            this.renderMenuSection(
              '_popular',
              'Популярное',
              highlightedProducts,
            ),
          );
        }
      }

      const menuGroups = _.groupBy(
        filteredProducts,
        (product) => (product.category && product.category.name) || 'Другое',
      );

      Object.entries(menuGroups).forEach(([groupName, groupProducts]) => {
        menuBlocks.push(
          this.renderMenuSection(groupName, groupName, groupProducts),
        );
      });
    }

    return (
      <React.Fragment>
        <NavBarComponent
          totalItems={totalItems}
          totalAmount={totalAmount}
          handleCartShow={this.handleCartShow}
        />

        {status && (
          <StatusBanner
            kind={status.kind}
            text={status.text}
            onClose={() => this.setState({ status: null })}
          />
        )}

        <CartModalComponent
          cartItems={cart}
          showCart={showCart}
          removeProduct={this.handleRemoveProduct}
          handleCartClose={this.handleCartClose}
          handleProceed={this.handleCheckoutModalShow}
        />

        {quickViewProduct && (
          <QuickView
            product={quickViewProduct}
            handleQuickViewModalClose={this.handleQuickViewModalClose}
          />
        )}

        {banners && banners.length > 0 && (
          <BannerComponent banners={banners} />
        )}

        <a id="menu" href="#"></a>

        <div className="container-fluid">
          <div className="row" style={{ marginBottom: '50px' }}>
            <div className="col-md-3  col-lg-3"></div>
            <div
              className="col-md-6 col-sm-12 col-lg-6 mt-5"
              style={{ marginTop: '50px' }}
            >
              <div className="input-group">
                <input
                  type="text"
                  onChange={this.handleSearch}
                  className="form-control"
                  aria-label="Поиск по меню"
                  placeholder="Найти блюдо"
                />
                <span
                  className="input-group-addon"
                  style={{ marginTop: '40px' }}
                >
                  <span className="glyphicon glyphicon-search"></span>
                </span>
              </div>
            </div>
            <div className="col-md-3 col-lg-3"></div>
          </div>

          {!products && !productsError && (
            <div>
              <center>
                <h2>Меню Star Burger</h2>
                <hr />
              </center>
              <LoadingProducts />
            </div>
          )}

          {productsError && (
            <div className="row">
              <div className="col-md-6 col-md-offset-3 text-center">
                <h2>Не удалось загрузить меню</h2>
                <p>Проверьте соединение и попробуйте ещё раз.</p>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={this.loadProducts}
                >
                  Обновить
                </button>
              </div>
            </div>
          )}

          {products && normalizedTerm && !menuBlocks.length && <NoResults />}

          {products && !normalizedTerm && !menuBlocks.length && (
            <div className="row">
              <div className="col-6">
                <center>
                  <h2>Меню пока пусто...</h2>
                </center>
              </div>
            </div>
          )}

          {menuBlocks}

          <br />
          <br />
          <br />
        </div>

        <a href="#" id="contact_us"></a>
        <FooterComponent />

        <CheckoutModal
          checkoutModalActive={checkoutModalActive}
          error={checkoutError}
          handleCheckoutModalClose={this.handleCheckoutModalClose}
          handleCheckout={this.handleCheckout}
        />
      </React.Fragment>
    );
  }
}

export default App;
