import type { PageProps } from "../types/appState";
import { formatCurrency } from "../lib/formatters";

export function ProductsPage({
  data,
  loading,
  productForm,
  productSubmitting,
  bulkSubmitting,
  onProductFormChange,
  onCreateOrUpdateProduct,
  onEditProduct,
  onDeleteProduct,
  onBulkDeleteProducts,
  editingProductId,
  selectedProductIds,
  onSelectedProductIdsChange,
}: PageProps) {
  return (
    <section className="stack">
      <form className="panel-card form-card" onSubmit={onCreateOrUpdateProduct}>
        <div className="form-header">
          <h3>{editingProductId ? "Edit Product" : "New Product"}</h3>
        </div>
        <div className="form-grid">
          <label>
            Name
            <input
              required
              value={productForm.name}
              onChange={(event) => onProductFormChange((current) => ({ ...current, name: event.target.value }))}
            />
          </label>
          <label>
            SKU
            <input
              required
              value={productForm.sku}
              onChange={(event) => onProductFormChange((current) => ({ ...current, sku: event.target.value }))}
            />
          </label>
          <label>
            Price
            <input
              required
              min="0"
              step="0.01"
              type="number"
              value={productForm.price}
              onChange={(event) => onProductFormChange((current) => ({ ...current, price: event.target.value }))}
            />
          </label>
          <label>
            Currency
            <input
              maxLength={3}
              value={productForm.currency}
              onChange={(event) => onProductFormChange((current) => ({ ...current, currency: event.target.value }))}
            />
          </label>
          <label className="full-span">
            Description
            <textarea
              rows={3}
              value={productForm.description}
              onChange={(event) =>
                onProductFormChange((current) => ({ ...current, description: event.target.value }))
              }
            />
          </label>
        </div>
        <div className="form-actions">
          <button className="primary-button" disabled={productSubmitting} type="submit">
            {productSubmitting ? "Saving..." : editingProductId ? "Update Product" : "Create Product"}
          </button>
        </div>
      </form>

      <div className="panel-card">
        <div className="form-header bulk-toolbar">
          <div>
            <h3>📦 Products</h3>
            <p className="subtle-text">{selectedProductIds.length} selected</p>
          </div>
          <button
            className="text-button danger"
            disabled={selectedProductIds.length === 0 || bulkSubmitting === "products"}
            onClick={() => void onBulkDeleteProducts()}
            type="button"
          >
            {bulkSubmitting === "products" ? "🗑️ Deleting..." : "🗑️ Bulk Delete"}
          </button>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>
                  <input
                    checked={data.products.length > 0 && selectedProductIds.length === data.products.length}
                    onChange={(event) =>
                      onSelectedProductIdsChange(event.target.checked ? data.products.map((product) => product.id) : [])
                    }
                    type="checkbox"
                  />
                </th>
                <th>Name</th>
                <th>SKU</th>
                <th>Price</th>
                <th>Description</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td className="empty-cell" colSpan={6}>
                    Loading products...
                  </td>
                </tr>
              ) : data.products.length === 0 ? (
                <tr>
                  <td className="empty-cell" colSpan={6}>
                    No products yet.
                  </td>
                </tr>
              ) : (
                data.products.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <input
                        checked={selectedProductIds.includes(product.id)}
                        onChange={(event) =>
                          onSelectedProductIdsChange((current) =>
                            event.target.checked
                              ? [...current, product.id]
                              : current.filter((id) => id !== product.id),
                          )
                        }
                        type="checkbox"
                      />
                    </td>
                    <td>{product.name}</td>
                    <td>{product.sku}</td>
                    <td>{formatCurrency(product.price, product.currency)}</td>
                    <td>{product.description ?? "-"}</td>
                    <td>
                      <div className="action-row">
                        <button className="text-button" onClick={() => onEditProduct(product)} type="button">
                          Edit
                        </button>
                        <button
                          className="text-button danger"
                          onClick={() => void onDeleteProduct(product.id)}
                          type="button"
                        >
                          🗑️ Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
