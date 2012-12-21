#include "pyutils.h"
#include "exception.h"

PyObject* PyArray_FromMatrixXf(const MatrixXf& mat) {
	// matrix dimensionality
	npy_intp dims[2];
	dims[0] = mat.rows();
	dims[1] = mat.cols();

	// allocate PyArray
	#ifdef EIGEN_DEFAULT_TO_ROW_MAJOR
	PyObject* array = PyArray_New(&PyArray_Type, 2, dims, NPY_FLOAT, 0, 0, sizeof(float), NPY_C_CONTIGUOUS, 0);
	#else
	PyObject* array = PyArray_New(&PyArray_Type, 2, dims, NPY_FLOAT, 0, 0, sizeof(float), NPY_F_CONTIGUOUS, 0);
	#endif

	// copy data
	const float* data = mat.data();
	float* dataCopy = reinterpret_cast<float*>(PyArray_DATA(array));

	for(int i = 0; i < mat.size(); ++i)
		dataCopy[i] = data[i];

	return array;
}



MatrixXf PyArray_ToMatrixXf(PyObject* array) {
	if(PyArray_DESCR(array)->type != PyArray_DescrFromType(NPY_FLOAT)->type)
		throw Exception("Can only handle arrays of float values.");

	if(PyArray_NDIM(array) == 1) {
		if(PyArray_FLAGS(array) & NPY_F_CONTIGUOUS)
			return Map<Matrix<float, Dynamic, Dynamic, ColMajor> >(
				reinterpret_cast<float*>(PyArray_DATA(array)),
				PyArray_DIM(array, 0), 1);

		else if(PyArray_FLAGS(array) & NPY_C_CONTIGUOUS)
			return Map<Matrix<float, Dynamic, Dynamic, RowMajor> >(
				reinterpret_cast<float*>(PyArray_DATA(array)),
				PyArray_DIM(array, 0), 1);

		else
			throw Exception("Data must be stored in contiguous memory.");

	} else if(PyArray_NDIM(array) == 2) {
		if(PyArray_FLAGS(array) & NPY_F_CONTIGUOUS)
			return Map<Matrix<float, Dynamic, Dynamic, ColMajor> >(
				reinterpret_cast<float*>(PyArray_DATA(array)),
				PyArray_DIM(array, 0),
				PyArray_DIM(array, 1));

		else if(PyArray_FLAGS(array) & NPY_C_CONTIGUOUS)
			return Map<Matrix<float, Dynamic, Dynamic, RowMajor> >(
				reinterpret_cast<float*>(PyArray_DATA(array)),
				PyArray_DIM(array, 0),
				PyArray_DIM(array, 1));

		else
			throw Exception("Data must be stored in contiguous memory.");

	} else {
		throw Exception("Can only handle one- or two-dimensional arrays.");
	}
}
