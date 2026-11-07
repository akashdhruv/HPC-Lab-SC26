! boundary.F90 -- guard cells of one field: periodic in x, periodic or Neumann in y.
subroutine apply_bc(f, nx, ny, bc_y)
   use kinds, only: rk
   implicit none
   integer, intent(in) :: nx, ny
   real(rk), intent(inout) :: f(0:nx+1, 0:ny+1)
   character(len=*), intent(in) :: bc_y

   f(0, 1:ny) = f(nx, 1:ny)
   f(nx+1, 1:ny) = f(1, 1:ny)
   select case (trim(bc_y))
   case ('periodic')
      f(:, 0) = f(:, ny)
      f(:, ny+1) = f(:, 1)
   case ('neumann')
      f(:, 0) = f(:, 1)
      f(:, ny+1) = f(:, ny)
   case default
      error stop "apply_bc: unknown bc_y"
   end select
end subroutine apply_bc
